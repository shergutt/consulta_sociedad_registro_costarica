#!/usr/bin/env python3
"""Ingest RNP analysis folder into PostgreSQL."""
import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_json(data):
    return json.dumps(data if data is not None else {}, ensure_ascii=False, sort_keys=True)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sibling(path, suffix):
    candidate = path.with_suffix(suffix)
    return candidate if candidate.exists() else None


def cedula_digits(raw):
    digits = re.sub(r"\D", "", raw or "")
    return digits or None


def extract_cedula(folder, report_text):
    folder_match = re.search(r"_(\d{9,12})$", folder.name)
    if folder_match:
        return folder_match.group(1)
    report_match = re.search(r"C[eé]dula consultada:\s*`?(\d{9,12})`?", report_text or "", re.IGNORECASE)
    if report_match:
        return report_match.group(1)
    return None


def extract_first_name(folder, cedula):
    name = folder.name
    if cedula and name.endswith("_" + cedula):
        name = name[: -(len(cedula) + 1)]
    return name.split("_")[0].strip().upper() or None


def money_number(value):
    match = re.search(r"([\d,.]+)", value or "")
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def extract_presentaciones(text):
    return sorted(set(re.findall(r"\b\d{3,4}-\d{5,8}-\d{2}\b(?!-\d{4}-\d{3})", text or "")))


def extract_citas(text):
    return sorted(set(re.findall(r"\b\d{3,4}-\d{4,8}-\d{2}-\d{4}-\d{3}\b", text or "")))


def province_code(summary):
    match = re.match(r"(\d+)", str(summary.get("provincia", "")).strip())
    if match:
        return match.group(1)
    params = summary.get("params") or {}
    return str(params.get("provincia") or summary.get("provincia_codigo") or "").strip()


def finca_stem(summary):
    return f"{province_code(summary)}_{summary.get('numero', '')}_{summary.get('derecho', '')}"


def rel_path(path, base):
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return str(Path(path).resolve())


QUERY_DIRS = {
    "finca_numero": "finca_numero",
    "catastro_planos": "catastro_plano",
    "historia_fincas": "historia_finca",
    "gravamenes_hipotecas": "gravamen_hipoteca",
    "documentos_diario": "documento_diario",
    "diario_defectos": "diario_defectos",
    "primeras_presentaciones": "primeras_presentaciones",
    "anotaciones_tramites": "anotaciones_tramites",
    "valores_finca": "valores_finca",
    "historia_gravamenes_inmuebles": "historia_gravamenes_inmuebles",
    "historia_bienes_muebles": "historia_bienes_muebles",
    "historia_presentaciones_muebles": "historia_presentaciones_muebles",
    "citas_presentacion_muebles": "citas_presentacion_muebles",
    "gravamenes_bienes_muebles": "gravamenes_bienes_muebles",
}


def load_fincas(folder):
    rows = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or "resumen" not in data or "detalle" not in data:
            continue
        resumen = data.get("resumen") or {}
        detalle = data.get("detalle") or {}
        rows.append({
            "path": path, "data": data, "resumen": resumen, "detalle": detalle,
            "txt_path": sibling(path, ".txt"), "html_path": sibling(path, ".html"),
        })
    return rows


def load_movable_assets(folder):
    rows = []
    target = folder / "bienes_muebles"
    if not target.exists():
        return rows
    for path in sorted(target.glob("*.json")):
        try:
            data = load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or "resumen" not in data or "detalle" not in data:
            continue
        resumen = data.get("resumen") or {}
        detalle = data.get("detalle") or {}
        rows.append({
            "path": path, "data": data, "resumen": resumen, "detalle": detalle,
            "txt_path": sibling(path, ".txt"), "html_path": sibling(path, ".html"),
        })
    return rows


def output_counts(folder):
    counts = {"finca_detalle": len(load_fincas(folder))}
    counts["bienes_muebles"] = len(load_movable_assets(folder))
    for subdir, query_type in QUERY_DIRS.items():
        target = folder / subdir
        counts[query_type] = len(list(target.glob("*.json"))) if target.exists() else 0
    return counts


def parse_report_counts(report_text):
    if not report_text:
        return {}
    counts = {}
    finca_match = re.search(r"Fincas encontradas:\s*`?(\d+)`?", report_text)
    alert_match = re.search(r"Alertas autom[aá]ticas:\s*`?(\d+)`?", report_text, re.IGNORECASE)
    if finca_match:
        counts["finca_count"] = int(finca_match.group(1))
    if alert_match:
        counts["alert_count"] = int(alert_match.group(1))
    return counts


def risk_flags(finca_records, folder):
    flags = []
    for record in finca_records:
        resumen = record["resumen"]
        detalle = record["detalle"]
        text = detalle.get("texto") or ""
        label = f"{resumen.get('provincia', '')} {resumen.get('numero', '')}".strip()

        gravamenes = (detalle.get("gravamenes") or "").strip()
        if gravamenes and gravamenes.upper() != "NO HAY":
            flags.append((record, label, "high", f"Grávámenes/afectaciones reportadas: {gravamenes}", "detalle.gravamenes"))

        upper_text = text.upper()
        for term in ("HIPOTECA", "SERVIDUMBRE", "CONDIC", "RESERV", "LIMITACIONES", "HABITACION FAMILIAR"):
            if term in upper_text:
                flags.append((record, label, "medium", f"El texto contiene indicador registral: {term}", "detalle.texto"))

        value = money_number(detalle.get("valor_fiscal") or "")
        if value is not None and value <= 1:
            flags.append((record, label, "medium", f"Valor fiscal sospechosamente bajo: {detalle.get('valor_fiscal')}", "detalle.valor_fiscal"))

        plano = detalle.get("plano")
        if plano and not (folder / "catastro_planos" / f"{plano}.json").exists():
            flags.append((record, label, "low", f"Falta salida de catastro para plano {plano}", "catastro_planos"))

        hist = folder / "historia_fincas" / f"{finca_stem(resumen)}.json"
        if not hist.exists():
            flags.append((record, label, "low", "Falta salida de historia de finca", "historia_fincas"))

        for presentacion in extract_presentaciones(text):
            if not (folder / "documentos_diario" / f"{presentacion}.json").exists():
                flags.append((record, label, "low", f"Falta salida de Diario para presentación {presentacion}", "documentos_diario"))

    return flags


def first_value(*values, default=None):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def ingest_folder(db_url, folder_path, cedula=None, user_id=None):
    folder = Path(folder_path).resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"No existe la carpeta de análisis: {folder}")

    report_path = folder / "analisis.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else None
    cedula = cedula_digits(cedula) or extract_cedula(folder, report_text)
    if not cedula:
        raise SystemExit("No pude detectar la cédula. Usa --cedula.")

    finca_records = load_fincas(folder)
    movable_records = load_movable_assets(folder)
    if not finca_records and not movable_records:
        raise SystemExit(f"No encontré JSONs de finca ni bienes muebles en: {folder}")

    owner = (
        (finca_records[0]["detalle"].get("propietario") if finca_records else None)
        or (movable_records[0]["detalle"].get("propietario") if movable_records else None)
        or (movable_records[0]["resumen"].get("nombre") if movable_records else None)
    )
    first_name = extract_first_name(folder, cedula)
    counts = output_counts(folder)
    parsed_counts = parse_report_counts(report_text)
    computed_alerts = len(risk_flags(finca_records, folder))
    finca_count = parsed_counts.get("finca_count", len(finca_records))
    alert_count = parsed_counts.get("alert_count", computed_alerts)
    timestamp = now_iso()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO persons (cedula, nombre, first_name, latest_folder_path, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (cedula) DO UPDATE SET
                nombre = COALESCE(EXCLUDED.nombre, persons.nombre),
                first_name = COALESCE(EXCLUDED.first_name, persons.first_name),
                latest_folder_path = EXCLUDED.latest_folder_path,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """, (cedula, owner, first_name, str(folder), timestamp, timestamp))
        person_id = cur.fetchone()[0]

        cur.execute("""
            SELECT id FROM analysis_runs WHERE person_id = %s AND folder_path = %s
        """, (person_id, str(folder)))
        existing = cur.fetchone()
        if existing:
            run_id = existing[0]
            cur.execute("""
                UPDATE analysis_runs SET cedula=%s, report_path=%s, report_markdown=%s,
                    finca_count=%s, alert_count=%s, output_counts_json=%s, ran_at=%s,
                    updated_at=%s, user_id=%s WHERE id=%s
            """, (cedula, str(report_path) if report_path.exists() else None,
                  report_text, finca_count, alert_count, safe_json(counts),
                  timestamp, timestamp, user_id, run_id))
        else:
            cur.execute("""
                INSERT INTO analysis_runs (person_id, user_id, cedula, folder_path, report_path,
                    report_markdown, finca_count, alert_count, output_counts_json, ran_at,
                    created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (person_id, user_id, cedula, str(folder),
                  str(report_path) if report_path.exists() else None,
                  report_text, finca_count, alert_count, safe_json(counts),
                  timestamp, timestamp, timestamp))
            run_id = cur.fetchone()[0]

        cur.execute("DELETE FROM alerts WHERE run_id = %s", (run_id,))
        cur.execute("DELETE FROM source_files WHERE run_id = %s", (run_id,))
        cur.execute("DELETE FROM movable_assets WHERE run_id = %s", (run_id,))
        cur.execute("""DELETE FROM finca_query_outputs
            WHERE query_output_id IN (SELECT id FROM query_outputs WHERE run_id = %s)""", (run_id,))
        cur.execute("""DELETE FROM finca_query_outputs
            WHERE finca_id IN (SELECT id FROM fincas WHERE run_id = %s)""", (run_id,))
        cur.execute("DELETE FROM query_outputs WHERE run_id = %s", (run_id,))
        cur.execute("DELETE FROM fincas WHERE run_id = %s", (run_id,))

        finca_ids = []
        for order, record in enumerate(finca_records, 1):
            resumen = record["resumen"]
            detalle = record["detalle"]
            index_no = resumen.get("index") or order
            cur.execute("""
                INSERT INTO fincas (run_id, index_no, provincia, provincia_codigo, numero,
                    derecho, duplicado, horizontal, matricula, naturaleza, ubicacion,
                    zona_catastrada, medida, plano, antecedentes, identificador_predial,
                    valor_fiscal_text, valor_fiscal_num, propietario, anotaciones, gravamenes,
                    resumen_json, detalle_json, texto, source_json, source_txt, source_html,
                    created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (run_id, index_no,
                  resumen.get("provincia") or detalle.get("provincia"),
                  province_code(resumen),
                  str(resumen.get("numero") or detalle.get("finca") or ""),
                  str(resumen.get("derecho") or detalle.get("derecho") or ""),
                  str(resumen.get("duplicado") or detalle.get("duplicado") or ""),
                  str(resumen.get("horizontal") or detalle.get("horizontal") or ""),
                  detalle.get("matricula"), detalle.get("naturaleza"),
                  detalle.get("ubicacion"), detalle.get("zona_catastrada"),
                  detalle.get("medida"), detalle.get("plano"),
                  detalle.get("antecedentes"), detalle.get("identificador_predial"),
                  detalle.get("valor_fiscal"), money_number(detalle.get("valor_fiscal") or ""),
                  detalle.get("propietario"), detalle.get("anotaciones"),
                  detalle.get("gravamenes"),
                  safe_json(resumen), safe_json(detalle), detalle.get("texto"),
                  rel_path(record["path"], folder),
                  rel_path(record["txt_path"], folder),
                  rel_path(record["html_path"], folder),
                  timestamp))
            finca_ids.append((cur.fetchone()[0], record))

        asset_count = 0
        for order, record in enumerate(movable_records, 1):
            resumen = record["resumen"]
            detalle = record["detalle"]
            numero = first_value(
                resumen.get("numero"), detalle.get("placa"), detalle.get("matricula"),
                detalle.get("serie"), detalle.get("vin"), detalle.get("motor"),
                resumen.get("identificacion"),
            )
            cur.execute("""
                INSERT INTO movable_assets (run_id, index_no, asset_type, identificacion,
                    nombre, tipo, numero, placa, matricula, marca, modelo, year, color,
                    serie, vin, motor, chasis, propietario, cedula_propietario, estado,
                    anotaciones, gravamenes, resumen_json, detalle_json, texto,
                    source_json, source_txt, source_html, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (run_id, resumen.get("index") or order, "bien_mueble",
                  resumen.get("identificacion"), resumen.get("nombre"),
                  first_value(resumen.get("tipo"), detalle.get("tipo"), detalle.get("categoria"), default="bien_mueble"),
                  numero, detalle.get("placa"), detalle.get("matricula"),
                  detalle.get("marca"),
                  first_value(detalle.get("modelo"), detalle.get("estilo")),
                  first_value(detalle.get("year"), detalle.get("anio")),
                  detalle.get("color"), detalle.get("serie"), detalle.get("vin"),
                  detalle.get("motor"), detalle.get("chasis"),
                  detalle.get("propietario"), detalle.get("cedula_propietario"),
                  first_value(resumen.get("estado"), detalle.get("estado")),
                  detalle.get("anotaciones"), detalle.get("gravamenes"),
                  safe_json(resumen), safe_json(detalle), detalle.get("texto"),
                  rel_path(record["path"], folder),
                  rel_path(record["txt_path"], folder),
                  rel_path(record["html_path"], folder),
                  timestamp))
            asset_count += 1

        output_count = 0
        for subdir, query_type in QUERY_DIRS.items():
            target = folder / subdir
            if not target.exists():
                continue
            for json_path in sorted(target.glob("*.json")):
                try:
                    payload = load_json(json_path)
                except (json.JSONDecodeError, OSError):
                    payload = {}
                lookup_key = json_path.stem
                txt_path = sibling(json_path, ".txt")
                html_path = sibling(json_path, ".html")
                cur.execute("""
                    INSERT INTO query_outputs (run_id, query_type, lookup_key, consulta,
                        entrada_json, origen_json, payload_json, texto, source_json,
                        source_txt, source_html, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (run_id, query_type, lookup_key,
                      payload.get("consulta") if isinstance(payload, dict) else None,
                      safe_json(payload.get("entrada")) if isinstance(payload, dict) else None,
                      safe_json(payload.get("origen")) if isinstance(payload, dict) else None,
                      safe_json(payload),
                      payload.get("texto") if isinstance(payload, dict) else None,
                      rel_path(json_path, folder),
                      rel_path(txt_path, folder),
                      rel_path(html_path, folder),
                      timestamp))
                query_id = cur.fetchone()[0]
                output_count += 1

                for finca_id, record in finca_ids:
                    resumen = record["resumen"]
                    detalle = record["detalle"]
                    text = detalle.get("texto") or ""
                    relation = None
                    if query_type == "catastro_plano" and detalle.get("plano") == lookup_key:
                        relation = "plano"
                    elif query_type == "finca_numero" and lookup_key == finca_stem(resumen):
                        relation = "finca"
                    elif query_type == "historia_finca" and finca_stem(resumen) == lookup_key:
                        relation = "finca"
                    elif query_type == "gravamen_hipoteca" and lookup_key in extract_citas(text):
                        relation = "cita"
                    elif query_type == "documento_diario" and lookup_key in extract_presentaciones(text):
                        relation = "presentacion"
                    elif query_type == "diario_defectos" and lookup_key in extract_presentaciones(text):
                        relation = "presentacion"
                    elif query_type == "primeras_presentaciones":
                        relation = "persona"
                    elif query_type == "anotaciones_tramites" and lookup_key in extract_presentaciones(text):
                        relation = "presentacion"
                    elif query_type == "valores_finca" and lookup_key.startswith(f"{province_code(resumen)}_{resumen.get('numero', '')}"):
                        relation = "finca"
                    elif query_type == "historia_gravamenes_inmuebles" and lookup_key in extract_citas(text):
                        relation = "cita"
                    if relation:
                        cur.execute("""INSERT INTO finca_query_outputs (finca_id, query_output_id, relation)
                            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                            (finca_id, query_id, relation))

        source_count = 0
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".txt", ".html", ".md"}:
                continue
            try:
                raw = path.read_bytes()
                content = raw.decode("utf-8", errors="replace")
            except OSError:
                continue
            cur.execute("""INSERT INTO source_files (run_id, relative_path, file_type,
                size_bytes, sha256, content_text, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, relative_path) DO UPDATE SET
                    file_type = EXCLUDED.file_type, size_bytes = EXCLUDED.size_bytes,
                    sha256 = EXCLUDED.sha256, content_text = EXCLUDED.content_text""",
                (run_id, rel_path(path, folder), path.suffix.lower().lstrip("."),
                 len(raw), hashlib.sha256(raw).hexdigest(), content, timestamp))
            source_count += 1

        flags = risk_flags(finca_records, folder)
        for idx, (record, label, severity, message, source) in enumerate(flags):
            finca_pk = next((fid for fid, rec in finca_ids if rec is record), None)
            cur.execute("""INSERT INTO alerts (run_id, finca_id, severity, label, message, source, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (run_id, finca_pk, severity, label, message, source, timestamp))
        inserted_alerts = len(flags)

        if inserted_alerts != alert_count:
            cur.execute("UPDATE analysis_runs SET alert_count = %s, updated_at = %s WHERE id = %s",
                        (inserted_alerts, timestamp, run_id))
            alert_count = inserted_alerts

        conn.commit()
        return {
            "person": owner or first_name or cedula,
            "cedula": cedula, "run_id": run_id,
            "finca_count": len(finca_records), "movable_asset_count": asset_count,
            "query_output_count": output_count, "source_file_count": source_count,
            "alert_count": alert_count,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="Carpeta con analisis.md y JSON/TXT/HTML")
    parser.add_argument("--cedula", help="Cédula consultada")
    parser.add_argument("--user-id", type=int, help="User ID for ownership")
    parser.add_argument("--db", default=os.environ.get("DATABASE_URL"),
                        help="PostgreSQL URL or 'postgresql' to use DATABASE_URL env var")
    args = parser.parse_args()

    db_url = args.db
    if db_url == "postgresql" or db_url == "pg":
        db_url = os.environ.get("DATABASE_URL")
    if not db_url or "postgresql" not in db_url:
        print("Error: --db must be a PostgreSQL URL or 'postgresql' (uses DATABASE_URL env)")
        sys.exit(1)

    result = ingest_folder(db_url, args.folder, cedula=args.cedula, user_id=args.user_id)
    print(f"PostgreSQL ingest: {result['person']} ({result['cedula']}) | "
          f"fincas={result['finca_count']} | muebles={result['movable_asset_count']} | "
          f"consultas={result['query_output_count']} | archivos={result['source_file_count']} | "
          f"alertas={result['alert_count']} | run_id={result['run_id']}")


if __name__ == "__main__":
    main()
