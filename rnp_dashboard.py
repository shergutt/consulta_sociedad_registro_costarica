#!/usr/bin/env python3
import argparse
import html
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


DEFAULT_DB = 'rnp_personas.sqlite'
DEFAULT_STATIC_DIR = 'dashboard'
DEFAULT_AI_MODEL = 'minimax-m3'
SKILL_RUNNER = Path.home() / '.codex/skills/analyze-rnp-cedula/scripts/build_rnp_report.py'


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_env_file(path):
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def json_loads(value, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        return json.loads(value or '')
    except (TypeError, json.JSONDecodeError):
        return fallback


def redact_secret(text, secret):
    value = str(text or '')
    if secret:
        value = value.replace(secret, '[REDACTED_MINIMAX_API_KEY]')
    return value


def extract_mmx_text(raw):
    raw = (raw or '').strip()
    if not raw:
        return ''
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False)

    for key in ('content', 'text', 'response', 'output'):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get('text') or item.get('content') or ''))
            if parts:
                return '\n'.join(part for part in parts if part)

    choices = payload.get('choices')
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get('message')
            if isinstance(message, dict) and isinstance(message.get('content'), str):
                return message['content']
            if isinstance(first.get('text'), str):
                return first['text']

    return json.dumps(payload, ensure_ascii=False)


def run_scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return 0
    return next(iter(dict(row).values()))


def latest_run_sql():
    return """
        SELECT id
        FROM analysis_runs
        WHERE person_id = p.id
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
    """


class Api:
    def __init__(self, db_path, project_dir='.', ai_model=DEFAULT_AI_MODEL, require_minimax=True):
        self.db_path = Path(db_path).resolve()
        self.project_dir = Path(project_dir).resolve()
        self.ai_model = ai_model
        self.require_minimax = require_minimax
        self.minimax_api_key = os.environ.get('MINIMAX_API_KEY')
        self.mmx_bin = shutil.which('mmx')
        self.jobs = {}
        self.jobs_lock = threading.Lock()

    def require_db(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f'No existe la base de datos: {self.db_path}')

    def summary(self):
        self.require_db()
        with connect(self.db_path) as conn:
            return {
                'db_path': str(self.db_path),
                'persons': run_scalar(conn, 'SELECT COUNT(*) AS total FROM persons'),
                'runs': run_scalar(conn, 'SELECT COUNT(*) AS total FROM analysis_runs'),
                'fincas': run_scalar(conn, 'SELECT COUNT(*) AS total FROM fincas'),
                'movable_assets': run_scalar(conn, 'SELECT COUNT(*) AS total FROM movable_assets'),
                'alerts': run_scalar(conn, 'SELECT COUNT(*) AS total FROM alerts'),
                'source_files': run_scalar(conn, 'SELECT COUNT(*) AS total FROM source_files'),
                'query_outputs': run_scalar(conn, 'SELECT COUNT(*) AS total FROM query_outputs'),
                'total_fiscal_value': run_scalar(conn, 'SELECT COALESCE(SUM(valor_fiscal_num), 0) AS total FROM fincas'),
            }

    def persons(self):
        self.require_db()
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.id AS person_id,
                    p.cedula,
                    COALESCE(p.nombre, p.first_name, '') AS nombre,
                    p.first_name,
                    p.latest_folder_path,
                    ar.id AS run_id,
                    ar.folder_path,
                    ar.report_path,
                    ar.finca_count,
                    ar.alert_count,
                    (
                        SELECT COUNT(*)
                        FROM movable_assets ma
                        WHERE ma.run_id = ar.id
                    ) AS movable_asset_count,
                    ar.output_counts_json,
                    ar.ran_at,
                    ar.updated_at
                FROM persons p
                LEFT JOIN analysis_runs ar ON ar.id = ({latest_run_sql()})
                ORDER BY ar.updated_at DESC, p.updated_at DESC
                """
            ).fetchall()
        people = rows_to_dicts(rows)
        for person in people:
            person['output_counts'] = json_loads(person.pop('output_counts_json', '{}'))
        return {'persons': people}

    def person_detail(self, cedula):
        self.require_db()
        cedula = re.sub(r'\D', '', cedula or '')
        if not cedula:
            raise ValueError('Cédula inválida')

        with connect(self.db_path) as conn:
            run = conn.execute(
                """
                SELECT
                    ar.*,
                    p.cedula AS person_cedula,
                    COALESCE(p.nombre, p.first_name, '') AS nombre,
                    p.first_name,
                    p.latest_folder_path
                FROM persons p
                JOIN analysis_runs ar ON ar.person_id = p.id
                WHERE p.cedula = ?
                ORDER BY ar.updated_at DESC, ar.id DESC
                LIMIT 1
                """,
                (cedula,),
            ).fetchone()
            if not run:
                raise LookupError(f'No hay datos para cédula {cedula}')

            run_id = run['id']
            fincas = conn.execute(
                """
                SELECT
                    f.id,
                    f.run_id,
                    f.index_no,
                    f.provincia,
                    f.provincia_codigo,
                    f.numero,
                    f.derecho,
                    f.duplicado,
                    f.horizontal,
                    f.matricula,
                    f.naturaleza,
                    f.ubicacion,
                    f.zona_catastrada,
                    f.medida,
                    f.plano,
                    f.antecedentes,
                    f.identificador_predial,
                    f.valor_fiscal_text,
                    f.valor_fiscal_num,
                    f.propietario,
                    f.anotaciones,
                    f.gravamenes,
                    f.source_json,
                    f.source_txt,
                    f.source_html,
                    f.created_at,
                    (
                        SELECT COUNT(*)
                        FROM alerts a
                        WHERE a.finca_id = f.id
                    ) AS alert_count,
                    (
                        SELECT COUNT(*)
                        FROM finca_query_outputs fqo
                        WHERE fqo.finca_id = f.id
                    ) AS linked_output_count
                FROM fincas f
                WHERE f.run_id = ?
                ORDER BY f.index_no, f.id
                """,
                (run_id,),
            ).fetchall()
            alerts = conn.execute(
                """
                SELECT a.*, f.numero AS finca_numero, f.derecho AS finca_derecho, f.provincia AS finca_provincia
                FROM alerts a
                LEFT JOIN fincas f ON f.id = a.finca_id
                WHERE a.run_id = ?
                ORDER BY
                    CASE a.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    a.id
                """,
                (run_id,),
            ).fetchall()
            outputs = conn.execute(
                """
                SELECT
                    q.id,
                    q.query_type,
                    q.lookup_key,
                    q.consulta,
                    q.source_json,
                    q.source_txt,
                    q.source_html,
                    q.created_at,
                    GROUP_CONCAT(f.numero || ':' || f.derecho, ', ') AS fincas
                FROM query_outputs q
                LEFT JOIN finca_query_outputs fqo ON fqo.query_output_id = q.id
                LEFT JOIN fincas f ON f.id = fqo.finca_id
                WHERE q.run_id = ?
                GROUP BY q.id
                ORDER BY q.query_type, q.lookup_key
                """,
                (run_id,),
            ).fetchall()
            movable_assets = conn.execute(
                """
                SELECT
                    id,
                    run_id,
                    index_no,
                    asset_type,
                    identificacion,
                    nombre,
                    tipo,
                    numero,
                    placa,
                    matricula,
                    marca,
                    modelo,
                    year,
                    color,
                    serie,
                    vin,
                    motor,
                    chasis,
                    propietario,
                    cedula_propietario,
                    estado,
                    anotaciones,
                    gravamenes,
                    source_json,
                    source_txt,
                    source_html,
                    created_at
                FROM movable_assets
                WHERE run_id = ?
                ORDER BY index_no, id
                """,
                (run_id,),
            ).fetchall()
            source_files = conn.execute(
                """
                SELECT id, relative_path, file_type, size_bytes, sha256, created_at
                FROM source_files
                WHERE run_id = ?
                ORDER BY relative_path
                """,
                (run_id,),
            ).fetchall()

        run_dict = dict(run)
        run_dict['output_counts'] = json_loads(run_dict.pop('output_counts_json', '{}'))
        return {
            'person': {
                'cedula': run_dict.pop('person_cedula'),
                'nombre': run_dict.pop('nombre'),
                'first_name': run_dict.pop('first_name'),
                'latest_folder_path': run_dict.pop('latest_folder_path'),
            },
            'analysis': run_dict,
            'fincas': rows_to_dicts(fincas),
            'movable_assets': rows_to_dicts(movable_assets),
            'alerts': rows_to_dicts(alerts),
            'query_outputs': rows_to_dicts(outputs),
            'source_files': rows_to_dicts(source_files),
        }

    def source_file(self, source_id):
        self.require_db()
        try:
            source_id = int(source_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('ID de archivo inválido') from exc

        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    sf.*,
                    ar.cedula,
                    p.nombre
                FROM source_files sf
                JOIN analysis_runs ar ON ar.id = sf.run_id
                JOIN persons p ON p.id = ar.person_id
                WHERE sf.id = ?
                """,
                (source_id,),
            ).fetchone()
        if not row:
            raise LookupError(f'No existe archivo fuente {source_id}')
        return dict(row)

    def search(self, term):
        self.require_db()
        term = (term or '').strip()
        if not term:
            return {'results': []}

        like = f'%{term}%'
        with connect(self.db_path) as conn:
            finca_rows = conn.execute(
                """
                SELECT
                    'finca' AS result_type,
                    p.cedula,
                    COALESCE(p.nombre, p.first_name, '') AS nombre,
                    f.provincia,
                    f.numero,
                    f.derecho,
                    f.plano,
                    f.naturaleza,
                    f.valor_fiscal_text,
                    ar.id AS run_id
                FROM fincas f
                JOIN analysis_runs ar ON ar.id = f.run_id
                JOIN persons p ON p.id = ar.person_id
                WHERE
                    p.cedula LIKE ?
                    OR p.nombre LIKE ?
                    OR f.numero LIKE ?
                    OR f.plano LIKE ?
                    OR f.naturaleza LIKE ?
                    OR f.ubicacion LIKE ?
                ORDER BY p.nombre, f.index_no
                LIMIT 80
                """,
                (like, like, like, like, like, like),
            ).fetchall()
            asset_rows = conn.execute(
                """
                SELECT
                    'bien_mueble' AS result_type,
                    p.cedula,
                    COALESCE(p.nombre, p.first_name, '') AS nombre,
                    ma.tipo,
                    ma.numero,
                    ma.placa,
                    ma.matricula,
                    ma.marca,
                    ma.modelo,
                    ma.year,
                    ma.serie,
                    ma.vin,
                    ma.motor,
                    ma.chasis,
                    ma.propietario,
                    ar.id AS run_id
                FROM movable_assets ma
                JOIN analysis_runs ar ON ar.id = ma.run_id
                JOIN persons p ON p.id = ar.person_id
                WHERE
                    p.cedula LIKE ?
                    OR p.nombre LIKE ?
                    OR ma.nombre LIKE ?
                    OR ma.propietario LIKE ?
                    OR ma.placa LIKE ?
                    OR ma.matricula LIKE ?
                    OR ma.serie LIKE ?
                    OR ma.vin LIKE ?
                    OR ma.motor LIKE ?
                    OR ma.chasis LIKE ?
                    OR ma.marca LIKE ?
                    OR ma.modelo LIKE ?
                ORDER BY p.nombre, ma.index_no
                LIMIT 80
                """,
                (like, like, like, like, like, like, like, like, like, like, like, like),
            ).fetchall()
        return {'results': rows_to_dicts(finca_rows) + rows_to_dicts(asset_rows)}

    def start_analysis(self, cedula, pausa=15.0, limite=None):
        digits = re.sub(r'\D', '', cedula or '')
        if not re.fullmatch(r'\d{9,12}', digits):
            raise ValueError('La cédula debe tener entre 9 y 12 dígitos.')
        if not SKILL_RUNNER.exists():
            raise FileNotFoundError(f'No existe el orquestador del skill: {SKILL_RUNNER}')
        if not self.project_dir.exists():
            raise FileNotFoundError(f'No existe el proyecto: {self.project_dir}')

        job_id = uuid.uuid4().hex[:12]
        created_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        job = {
            'id': job_id,
            'cedula': digits,
            'ai_model': self.ai_model,
            'status': 'queued',
            'created_at': created_at,
            'updated_at': created_at,
            'started_at': None,
            'finished_at': None,
            'returncode': None,
            'command': None,
            'log': [],
            'error': None,
            'person': None,
        }
        with self.jobs_lock:
            self.jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_analysis_job,
            args=(job_id, digits, pausa, limite),
            daemon=True,
        )
        thread.start()
        return self.job(job_id)

    def list_jobs(self):
        with self.jobs_lock:
            jobs = [self._public_job(job, include_log=False) for job in self.jobs.values()]
        jobs.sort(key=lambda item: item['created_at'], reverse=True)
        return {'jobs': jobs}

    def job(self, job_id):
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                raise LookupError(f'No existe job {job_id}')
            return self._public_job(job, include_log=True)

    def _public_job(self, job, include_log):
        payload = {key: value for key, value in job.items() if key != 'log'}
        payload['log_tail'] = job['log'][-220:] if include_log else job['log'][-25:]
        return payload

    def _update_job(self, job_id, **changes):
        changes['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        with self.jobs_lock:
            self.jobs[job_id].update(changes)

    def _append_job_log(self, job_id, line):
        with self.jobs_lock:
            job = self.jobs[job_id]
            job['log'].append(line.rstrip())
            if len(job['log']) > 1200:
                job['log'] = job['log'][-1200:]
            job['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')

    def _run_analysis_job(self, job_id, cedula, pausa, limite):
        started_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        cmd = [
            sys.executable,
            '-u',
            str(SKILL_RUNNER),
            cedula,
            '--project',
            str(self.project_dir),
            '--db',
            str(self.db_path),
            '--pausa',
            str(pausa),
        ]
        if limite is not None:
            cmd.extend(['--limite', str(limite)])

        self._update_job(job_id, status='running', started_at=started_at, command=cmd)
        self._append_job_log(job_id, f'AI runner: {self.ai_model}')
        self._append_job_log(job_id, f'Cédula: {cedula}')

        try:
            ai_decision = self._minimax_preflight(cedula)
            self._append_job_log(job_id, f'MiniMax autorizó acción: {ai_decision.get("action")}')
            if ai_decision.get('reason'):
                self._append_job_log(job_id, f'MiniMax: {ai_decision["reason"]}')
            self._append_job_log(job_id, 'Ejecutando skill analyze-rnp-cedula...')
            proc = subprocess.Popen(
                cmd,
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self._append_job_log(job_id, line)
            returncode = proc.wait()
            finished_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
            if returncode == 0:
                person = None
                try:
                    person = self.person_detail(cedula)['person']
                except (FileNotFoundError, LookupError, ValueError, sqlite3.Error) as exc:
                    self._append_job_log(job_id, f'Análisis terminó, pero no pude leer la persona desde SQLite: {exc}')
                self._update_job(
                    job_id,
                    status='succeeded',
                    returncode=returncode,
                    finished_at=finished_at,
                    person=person,
                )
                self._append_job_log(job_id, 'Job completado y base SQLite actualizada.')
            else:
                self._update_job(
                    job_id,
                    status='failed',
                    returncode=returncode,
                    finished_at=finished_at,
                    error=f'El orquestador terminó con código {returncode}.',
                )
        except Exception as exc:
            self._update_job(
                job_id,
                status='failed',
                finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                error=str(exc),
            )
            self._append_job_log(job_id, f'ERROR: {exc}')

    def _minimax_preflight(self, cedula):
        if not self.require_minimax:
            return {
                'action': 'run_analyze_rnp_cedula',
                'cedula': cedula,
                'reason': 'MiniMax preflight desactivado por configuración local.',
            }
        if not self.mmx_bin:
            raise RuntimeError('No encontré el binario mmx. Instalá mmx-cli o ajustá PATH.')

        system = (
            'You are a strict local task router. Return JSON only. '
            'Do not include markdown. Do not request secrets. '
            'Only authorize the exact local RNP analysis skill for valid digit-only cedula input.'
        )
        message = (
            'Validate this Costa Rica cedula input and authorize the local workflow. '
            'Return exactly this JSON shape: '
            '{"action":"run_analyze_rnp_cedula","cedula":"DIGITS","reason":"short Spanish reason"}. '
            f'Input cedula: {cedula}'
        )
        env = os.environ.copy()
        if self.minimax_api_key:
            env['MINIMAX_API_KEY'] = self.minimax_api_key
        env['NO_COLOR'] = '1'
        cmd = [
            self.mmx_bin,
            '--output',
            'json',
            '--quiet',
            '--non-interactive',
            '--timeout',
            '90',
            'text',
            'chat',
            '--model',
            self.ai_model,
            '--system',
            system,
            '--message',
            f'user:{message}',
            '--max-tokens',
            '300',
            '--temperature',
            '0.1',
        ]
        if self.minimax_api_key:
            cmd[1:1] = ['--api-key', self.minimax_api_key]
        proc = subprocess.run(
            cmd,
            cwd=self.project_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if proc.returncode != 0:
            stderr = redact_secret(proc.stderr.strip(), self.minimax_api_key)
            raise RuntimeError(f'MiniMax falló antes de ejecutar el skill: {stderr or "sin detalle"}')

        content = extract_mmx_text(proc.stdout)
        content = redact_secret(content, self.minimax_api_key)
        match = re.search(r'\{.*\}', content, re.S)
        if not match:
            raise RuntimeError(f'MiniMax no devolvió JSON autorizable: {content[:400]}')
        try:
            decision = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f'MiniMax devolvió JSON inválido: {content[:400]}') from exc
        if decision.get('action') != 'run_analyze_rnp_cedula':
            raise RuntimeError(f'MiniMax no autorizó el workflow: {decision}')
        if re.sub(r'\D', '', str(decision.get('cedula') or '')) != cedula:
            raise RuntimeError('MiniMax devolvió una cédula distinta a la solicitada.')
        return decision


def make_handler(api, static_dir):
    static_root = Path(static_dir).resolve()

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = 'RNPDashboard/1.0'

        def log_message(self, fmt, *args):
            print('%s - - [%s] %s' % (self.address_string(), self.log_date_time_string(), fmt % args))

        def send_json(self, payload, status=200):
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def send_error_json(self, status, message):
            self.send_json({'error': message}, status=status)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            try:
                if path.startswith('/api/'):
                    self.handle_api(path, query)
                else:
                    self.handle_static(path)
            except FileNotFoundError as exc:
                self.send_error_json(404, str(exc))
            except LookupError as exc:
                self.send_error_json(404, str(exc))
            except ValueError as exc:
                self.send_error_json(400, str(exc))
            except sqlite3.Error as exc:
                self.send_error_json(500, f'Error SQLite: {exc}')

        def do_HEAD(self):
            self.do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            try:
                if not path.startswith('/api/'):
                    self.send_error_json(404, f'Endpoint no encontrado: {html.escape(path)}')
                    return
                payload = self.read_json_body()
                self.handle_api_post(path, payload)
            except FileNotFoundError as exc:
                self.send_error_json(404, str(exc))
            except LookupError as exc:
                self.send_error_json(404, str(exc))
            except ValueError as exc:
                self.send_error_json(400, str(exc))
            except sqlite3.Error as exc:
                self.send_error_json(500, f'Error SQLite: {exc}')

        def read_json_body(self):
            length = int(self.headers.get('Content-Length') or 0)
            if length > 100_000:
                raise ValueError('Payload demasiado grande.')
            raw = self.rfile.read(length) if length else b'{}'
            try:
                payload = json.loads(raw.decode('utf-8') or '{}')
            except json.JSONDecodeError as exc:
                raise ValueError('JSON inválido.') from exc
            if not isinstance(payload, dict):
                raise ValueError('El payload debe ser un objeto JSON.')
            return payload

        def handle_api(self, path, query):
            if path == '/api/summary':
                self.send_json(api.summary())
                return
            if path == '/api/persons':
                self.send_json(api.persons())
                return
            if path.startswith('/api/persons/'):
                cedula = path.rsplit('/', 1)[-1]
                self.send_json(api.person_detail(cedula))
                return
            if path.startswith('/api/source-files/'):
                source_id = path.rsplit('/', 1)[-1]
                self.send_json(api.source_file(source_id))
                return
            if path == '/api/search':
                term = query.get('q', [''])[0]
                self.send_json(api.search(term))
                return
            if path == '/api/jobs':
                self.send_json(api.list_jobs())
                return
            if path.startswith('/api/jobs/'):
                job_id = path.rsplit('/', 1)[-1]
                self.send_json(api.job(job_id))
                return
            self.send_error_json(404, f'Endpoint no encontrado: {html.escape(path)}')

        def handle_api_post(self, path, payload):
            if path == '/api/run-analysis':
                pausa = float(payload.get('pausa') or 15.0)
                limite = payload.get('limite')
                if limite in ('', None):
                    limite = None
                else:
                    limite = int(limite)
                if pausa < 0:
                    raise ValueError('La pausa no puede ser negativa.')
                self.send_json(api.start_analysis(payload.get('cedula'), pausa=pausa, limite=limite), status=202)
                return
            self.send_error_json(404, f'Endpoint no encontrado: {html.escape(path)}')

        def handle_static(self, path):
            if path in ('', '/'):
                target = static_root / 'index.html'
            else:
                requested = (static_root / path.lstrip('/')).resolve()
                if static_root not in requested.parents and requested != static_root:
                    self.send_error_json(403, 'Ruta estática no permitida')
                    return
                target = requested

            if not target.exists() or not target.is_file():
                self.send_error_json(404, f'Archivo no encontrado: {path}')
                return

            content_type = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
            body = target.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

    return DashboardHandler


def main():
    parser = argparse.ArgumentParser(description='Dashboard local para rnp_personas.sqlite.')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Ruta SQLite. Default: {DEFAULT_DB}')
    parser.add_argument('--static-dir', default=DEFAULT_STATIC_DIR, help=f'Carpeta frontend. Default: {DEFAULT_STATIC_DIR}')
    parser.add_argument('--project', default='.', help='Directorio del proyecto RNP. Default: .')
    parser.add_argument('--ai-model', default=DEFAULT_AI_MODEL, help=f'Modelo mostrado para el runner. Default: {DEFAULT_AI_MODEL}')
    parser.add_argument('--no-minimax', action='store_true', help='Ejecutar jobs sin preflight de MiniMax')
    parser.add_argument('--host', default='127.0.0.1', help='Host de escucha. Default: 127.0.0.1')
    parser.add_argument('--port', type=int, default=8765, help='Puerto local. Default: 8765')
    args = parser.parse_args()

    project = Path(args.project).resolve()
    load_env_file(project / '.env')

    api = Api(args.db, project_dir=project, ai_model=args.ai_model, require_minimax=not args.no_minimax)
    handler = make_handler(api, args.static_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f'Dashboard: http://{args.host}:{args.port}')
    print(f'Database : {Path(args.db).resolve()}')
    print(f'AI model : {args.ai_model}')
    print(f'MiniMax  : {"enabled" if not args.no_minimax else "disabled"}')
    print('Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping dashboard.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
