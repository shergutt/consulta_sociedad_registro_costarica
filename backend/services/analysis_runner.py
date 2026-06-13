import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from config import get_settings

settings = get_settings()

SKILL_RUNNER = Path.home() / ".codex/skills/analyze-rnp-cedula/scripts/build_rnp_report.py"

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _update_job(job_id: str, **changes) -> None:
    changes["updated_at"] = _now_iso()
    with _jobs_lock:
        _jobs[job_id].update(changes)


def _append_log(job_id: str, line: str) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job["log"].append(line.rstrip())
        if len(job["log"]) > 1200:
            job["log"] = job["log"][-1200:]
        job["updated_at"] = _now_iso()


def _public_job(job: dict, include_log: bool) -> dict:
    payload = {k: v for k, v in job.items() if k != "log"}
    payload["log_tail"] = job["log"][-220:] if include_log else job["log"][-25:]
    return payload


def _redact(text: str, secret: str | None) -> str:
    value = str(text or "")
    if secret:
        value = value.replace(secret, "[REDACTED]")
    return value


def _extract_mmx_text(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False)
    for key in ("content", "text", "response", "output"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"]
    return json.dumps(payload, ensure_ascii=False)


def _minimax_preflight(cedula: str) -> dict:
    if not settings.require_minimax:
        return {"action": "run_analyze_rnp_cedula", "cedula": cedula, "reason": "MiniMax preflight disabled."}

    mmx_bin = shutil.which("mmx")
    if not mmx_bin:
        raise RuntimeError("No encontré el binario mmx.")

    system = (
        "You are a strict local task router. Return JSON only. "
        "Do not include markdown. Do not request secrets. "
        "Only authorize the exact local RNP analysis skill for valid digit-only cedula input."
    )
    message = (
        "Validate this Costa Rica cedula input and authorize the local workflow. "
        "Return exactly this JSON shape: "
        '{"action":"run_analyze_rnp_cedula","cedula":"DIGITS","reason":"short Spanish reason"}. '
        f"Input cedula: {cedula}"
    )

    env = os.environ.copy()
    if settings.minimax_api_key:
        env["MINIMAX_API_KEY"] = settings.minimax_api_key
    env["NO_COLOR"] = "1"

    cmd = [
        mmx_bin, "--output", "json", "--quiet", "--non-interactive",
        "--timeout", "90", "text", "chat",
        "--model", settings.ai_model,
        "--system", system, "--message", f"user:{message}",
        "--max-tokens", "300", "--temperature", "0.1",
    ]
    if settings.minimax_api_key:
        cmd[1:1] = ["--api-key", settings.minimax_api_key]

    proc = subprocess.run(
        cmd, cwd=settings.project_dir, env=env,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"MiniMax falló: {_redact(proc.stderr.strip(), settings.minimax_api_key)}")

    content = _extract_mmx_text(proc.stdout)
    content = _redact(content, settings.minimax_api_key)
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise RuntimeError(f"MiniMax no devolvió JSON: {content[:400]}")
    decision = json.loads(match.group(0))
    if decision.get("action") != "run_analyze_rnp_cedula":
        raise RuntimeError(f"MiniMax no autorizó: {decision}")
    return decision


def _run_job(job_id: str, cedula: str, pausa: float, limite: int | None) -> None:
    started_at = _now_iso()
    project_dir = settings.project_dir
    cmd = [
        sys.executable, "-u", str(SKILL_RUNNER), cedula,
        "--project", str(project_dir),
        "--db", "postgresql",
        "--pausa", str(pausa),
    ]
    if limite is not None:
        cmd.extend(["--limite", str(limite)])

    _update_job(job_id, status="running", started_at=started_at, command=cmd)
    _append_log(job_id, f"AI runner: {settings.ai_model}")
    _append_log(job_id, f"Cédula: {cedula}")

    try:
        decision = _minimax_preflight(cedula)
        _append_log(job_id, f"MiniMax autorizó: {decision.get('action')}")
        if decision.get("reason"):
            _append_log(job_id, f"MiniMax: {decision['reason']}")
        _append_log(job_id, "Ejecutando skill analyze-rnp-cedula...")

        sub_env = os.environ.copy()
        sub_env["RNP_USER"] = settings.rnp_user
        sub_env["RNP_PASS"] = settings.rnp_pass
        sub_env["MINIMAX_API_KEY"] = settings.minimax_api_key
        sub_env["DATABASE_URL"] = settings.database_url
        sub_env["NO_COLOR"] = "1"

        proc = subprocess.Popen(
            cmd, cwd=settings.project_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=sub_env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            _append_log(job_id, line)
        returncode = proc.wait()
        finished_at = _now_iso()

        if returncode == 0:
            _update_job(job_id, status="succeeded", returncode=returncode, finished_at=finished_at)
            _append_log(job_id, "Job completado.")
        else:
            _update_job(job_id, status="failed", returncode=returncode, finished_at=finished_at,
                        error=f"El orquestador terminó con código {returncode}.")
    except Exception as exc:
        _update_job(job_id, status="failed", finished_at=_now_iso(), error=str(exc))
        _append_log(job_id, f"ERROR: {exc}")


def start_analysis(cedula: str, user_id: int | None, pausa: float = 15.0, limite: int | None = None) -> dict:
    digits = re.sub(r"\D", "", cedula or "")
    if not re.fullmatch(r"\d{9,12}", digits):
        raise ValueError("La cédula debe tener entre 9 y 12 dígitos.")
    if not SKILL_RUNNER.exists():
        raise FileNotFoundError(f"No existe el orquestador: {SKILL_RUNNER}")

    from database import SessionLocal
    from models import Person, PersonQuery

    person_id: int | None = None
    db = SessionLocal()
    try:
        person = db.query(Person).filter(Person.cedula == digits).first()
        if person is None:
            person = Person(cedula=digits, latest_folder_path="")
            db.add(person)
            db.flush()
        person_id = person.id
        if user_id is not None:
            already = (
                db.query(PersonQuery)
                .filter(PersonQuery.person_id == person_id, PersonQuery.user_id == user_id)
                .first()
            )
            if already is None:
                db.add(PersonQuery(person_id=person_id, user_id=user_id))
                db.commit()
            else:
                db.rollback()
    finally:
        db.close()

    job_id = uuid.uuid4().hex[:12]
    created_at = _now_iso()
    job = {
        "id": job_id, "user_id": user_id, "cedula": digits,
        "person_id": person_id,
        "ai_model": settings.ai_model, "status": "queued",
        "created_at": created_at, "updated_at": created_at,
        "started_at": None, "finished_at": None, "returncode": None,
        "command": None, "log": [], "error": None, "person": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run_job, args=(job_id, digits, pausa, limite), daemon=True)
    thread.start()
    return get_job(job_id, user_id=user_id, include_log=True)


def list_jobs(user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    with _jobs_lock:
        if user_id and not is_admin:
            jobs = [_public_job(j, include_log=False) for j in _jobs.values() if j.get("user_id") == user_id]
        else:
            jobs = [_public_job(j, include_log=False) for j in _jobs.values()]
    jobs.sort(key=lambda x: x["created_at"], reverse=True)
    return jobs


def get_job(job_id: str, user_id: int | None = None, is_admin: bool = False, include_log: bool = True) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise LookupError(f"No existe job {job_id}")
    if user_id and not is_admin and job.get("user_id") != user_id:
        raise PermissionError("No tenés permiso para ver este job")
    return _public_job(job, include_log=include_log)
