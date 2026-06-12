#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB = 'rnp_personas.sqlite'

QUERY_DIRS = {
    'finca_numero': 'finca_numero',
    'catastro_planos': 'catastro_plano',
    'historia_fincas': 'historia_finca',
    'gravamenes_hipotecas': 'gravamen_hipoteca',
    'documentos_diario': 'documento_diario',
    'diario_defectos': 'diario_defectos',
    'primeras_presentaciones': 'primeras_presentaciones',
    'anotaciones_tramites': 'anotaciones_tramites',
    'valores_finca': 'valores_finca',
    'historia_gravamenes_inmuebles': 'historia_gravamenes_inmuebles',
    'historia_bienes_muebles': 'historia_bienes_muebles',
    'historia_presentaciones_muebles': 'historia_presentaciones_muebles',
    'citas_presentacion_muebles': 'citas_presentacion_muebles',
    'gravamenes_bienes_muebles': 'gravamenes_bienes_muebles',
}


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cedula TEXT NOT NULL UNIQUE,
    nombre TEXT,
    first_name TEXT,
    latest_folder_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    cedula TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    report_path TEXT,
    report_markdown TEXT,
    finca_count INTEGER NOT NULL DEFAULT 0,
    alert_count INTEGER NOT NULL DEFAULT 0,
    output_counts_json TEXT NOT NULL DEFAULT '{}',
    ran_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(person_id, folder_path)
);

CREATE TABLE IF NOT EXISTS fincas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    index_no INTEGER,
    provincia TEXT,
    provincia_codigo TEXT,
    numero TEXT,
    derecho TEXT,
    duplicado TEXT,
    horizontal TEXT,
    matricula TEXT,
    naturaleza TEXT,
    ubicacion TEXT,
    zona_catastrada TEXT,
    medida TEXT,
    plano TEXT,
    antecedentes TEXT,
    identificador_predial TEXT,
    valor_fiscal_text TEXT,
    valor_fiscal_num REAL,
    propietario TEXT,
    anotaciones TEXT,
    gravamenes TEXT,
    resumen_json TEXT NOT NULL,
    detalle_json TEXT NOT NULL,
    texto TEXT,
    source_json TEXT,
    source_txt TEXT,
    source_html TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fincas_run ON fincas(run_id);
CREATE INDEX IF NOT EXISTS idx_fincas_numero ON fincas(numero);
CREATE INDEX IF NOT EXISTS idx_fincas_plano ON fincas(plano);

CREATE TABLE IF NOT EXISTS movable_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    index_no INTEGER,
    asset_type TEXT NOT NULL DEFAULT 'bien_mueble',
    identificacion TEXT,
    nombre TEXT,
    tipo TEXT,
    numero TEXT,
    placa TEXT,
    matricula TEXT,
    marca TEXT,
    modelo TEXT,
    year TEXT,
    color TEXT,
    serie TEXT,
    vin TEXT,
    motor TEXT,
    chasis TEXT,
    propietario TEXT,
    cedula_propietario TEXT,
    estado TEXT,
    anotaciones TEXT,
    gravamenes TEXT,
    resumen_json TEXT NOT NULL,
    detalle_json TEXT NOT NULL,
    texto TEXT,
    source_json TEXT,
    source_txt TEXT,
    source_html TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_movable_assets_run ON movable_assets(run_id);
CREATE INDEX IF NOT EXISTS idx_movable_assets_lookup ON movable_assets(placa, serie, vin, motor, chasis);

CREATE TABLE IF NOT EXISTS query_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    query_type TEXT NOT NULL,
    lookup_key TEXT NOT NULL,
    consulta TEXT,
    entrada_json TEXT,
    origen_json TEXT,
    payload_json TEXT,
    texto TEXT,
    source_json TEXT,
    source_txt TEXT,
    source_html TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_query_outputs_run ON query_outputs(run_id);
CREATE INDEX IF NOT EXISTS idx_query_outputs_type_key ON query_outputs(query_type, lookup_key);

CREATE TABLE IF NOT EXISTS finca_query_outputs (
    finca_id INTEGER NOT NULL REFERENCES fincas(id) ON DELETE CASCADE,
    query_output_id INTEGER NOT NULL REFERENCES query_outputs(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    PRIMARY KEY (finca_id, query_output_id, relation)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    finca_id INTEGER REFERENCES fincas(id) ON DELETE SET NULL,
    severity TEXT NOT NULL,
    label TEXT,
    message TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_run ON alerts(run_id);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    content_text TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_source_files_run ON source_files(run_id);
"""


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)


def safe_json(data):
    return json.dumps(data if data is not None else {}, ensure_ascii=False, sort_keys=True)


def safe_read_text(path):
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def rel_path(path, base):
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(base.resolve()))
    except ValueError:
        return str(Path(path).resolve())


def sibling(path, suffix):
    candidate = path.with_suffix(suffix)
    return candidate if candidate.exists() else None


def cedula_digits(raw):
    digits = re.sub(r'\D', '', raw or '')
    return digits or None


def extract_cedula(folder, report_text):
    folder_match = re.search(r'_(\d{9,12})$', folder.name)
    if folder_match:
        return folder_match.group(1)
    report_match = re.search(r'C[eé]dula consultada:\s*`?(\d{9,12})`?', report_text or '', re.IGNORECASE)
    if report_match:
        return report_match.group(1)
    return None


def extract_first_name(folder, cedula):
    name = folder.name
    if cedula and name.endswith('_' + cedula):
        name = name[: -(len(cedula) + 1)]
    return name.split('_')[0].strip().upper() or None


def money_number(value):
    match = re.search(r'([\d,.]+)', value or '')
    if not match:
        return None
    try:
        return float(match.group(1).replace(',', ''))
    except ValueError:
        return None


def extract_presentaciones(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{5,8}-\d{2}\b(?!-\d{4}-\d{3})', text or '')))


def extract_citas(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{4,8}-\d{2}-\d{4}-\d{3}\b', text or '')))


def province_code(summary):
    match = re.match(r'(\d+)', str(summary.get('provincia', '')).strip())
    if match:
        return match.group(1)
    params = summary.get('params') or {}
    return str(params.get('provincia') or summary.get('provincia_codigo') or '').strip()


def finca_stem(summary):
    return f"{province_code(summary)}_{summary.get('numero', '')}_{summary.get('derecho', '')}"


def load_fincas(folder):
    rows = []
    for path in sorted(folder.glob('*.json')):
        try:
            data = load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or 'resumen' not in data or 'detalle' not in data:
            continue
        resumen = data.get('resumen') or {}
        detalle = data.get('detalle') or {}
        rows.append(
            {
                'path': path,
                'data': data,
                'resumen': resumen,
                'detalle': detalle,
                'txt_path': sibling(path, '.txt'),
                'html_path': sibling(path, '.html'),
            }
        )
    return rows


def load_movable_assets(folder):
    rows = []
    target = folder / 'bienes_muebles'
    if not target.exists():
        return rows
    for path in sorted(target.glob('*.json')):
        try:
            data = load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or 'resumen' not in data or 'detalle' not in data:
            continue
        resumen = data.get('resumen') or {}
        detalle = data.get('detalle') or {}
        rows.append(
            {
                'path': path,
                'data': data,
                'resumen': resumen,
                'detalle': detalle,
                'txt_path': sibling(path, '.txt'),
                'html_path': sibling(path, '.html'),
            }
        )
    return rows


def output_counts(folder):
    counts = {'finca_detalle': len(load_fincas(folder))}
    counts['bienes_muebles'] = len(load_movable_assets(folder))
    for subdir, query_type in QUERY_DIRS.items():
        target = folder / subdir
        counts[query_type] = len(list(target.glob('*.json'))) if target.exists() else 0
    return counts


def parse_report_counts(report_text):
    if not report_text:
        return {}
    counts = {}
    finca_match = re.search(r'Fincas encontradas:\s*`?(\d+)`?', report_text)
    alert_match = re.search(r'Alertas autom[aá]ticas:\s*`?(\d+)`?', report_text, re.IGNORECASE)
    if finca_match:
        counts['finca_count'] = int(finca_match.group(1))
    if alert_match:
        counts['alert_count'] = int(alert_match.group(1))
    return counts


def risk_flags(finca_records, folder):
    flags = []
    for record in finca_records:
        resumen = record['resumen']
        detalle = record['detalle']
        text = detalle.get('texto') or ''
        label = f"{resumen.get('provincia', '')} {resumen.get('numero', '')}".strip()

        gravamenes = (detalle.get('gravamenes') or '').strip()
        if gravamenes and gravamenes.upper() != 'NO HAY':
            flags.append((record, label, 'high', f'Gravámenes/afectaciones reportadas: {gravamenes}', 'detalle.gravamenes'))

        upper_text = text.upper()
        for term in ('HIPOTECA', 'SERVIDUMBRE', 'CONDIC', 'RESERV', 'LIMITACIONES', 'HABITACION FAMILIAR'):
            if term in upper_text:
                flags.append((record, label, 'medium', f'El texto contiene indicador registral: {term}', 'detalle.texto'))

        value = money_number(detalle.get('valor_fiscal') or '')
        if value is not None and value <= 1:
            flags.append((record, label, 'medium', f"Valor fiscal sospechosamente bajo: {detalle.get('valor_fiscal')}", 'detalle.valor_fiscal'))

        plano = detalle.get('plano')
        if plano and not (folder / 'catastro_planos' / f'{plano}.json').exists():
            flags.append((record, label, 'low', f'Falta salida de catastro para plano {plano}', 'catastro_planos'))

        hist = folder / 'historia_fincas' / f'{finca_stem(resumen)}.json'
        if not hist.exists():
            flags.append((record, label, 'low', 'Falta salida de historia de finca', 'historia_fincas'))

        for presentacion in extract_presentaciones(text):
            if not (folder / 'documentos_diario' / f'{presentacion}.json').exists():
                flags.append((record, label, 'low', f'Falta salida de Diario para presentación {presentacion}', 'documentos_diario'))

    return flags


def upsert_person(conn, cedula, nombre, first_name, folder_path, timestamp):
    conn.execute(
        """
        INSERT INTO persons (cedula, nombre, first_name, latest_folder_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(cedula) DO UPDATE SET
            nombre = COALESCE(excluded.nombre, persons.nombre),
            first_name = COALESCE(excluded.first_name, persons.first_name),
            latest_folder_path = excluded.latest_folder_path,
            updated_at = excluded.updated_at
        """,
        (cedula, nombre, first_name, str(folder_path), timestamp, timestamp),
    )
    return conn.execute('SELECT id FROM persons WHERE cedula = ?', (cedula,)).fetchone()['id']


def upsert_run(conn, person_id, cedula, folder, report_path, report_text, finca_count, alert_count, counts, timestamp):
    existing = conn.execute(
        'SELECT id, created_at FROM analysis_runs WHERE person_id = ? AND folder_path = ?',
        (person_id, str(folder)),
    ).fetchone()
    if existing:
        run_id = existing['id']
        conn.execute(
            """
            UPDATE analysis_runs
            SET cedula = ?, report_path = ?, report_markdown = ?, finca_count = ?,
                alert_count = ?, output_counts_json = ?, ran_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                cedula,
                str(report_path) if report_path else None,
                report_text,
                finca_count,
                alert_count,
                safe_json(counts),
                timestamp,
                timestamp,
                run_id,
            ),
        )
        return run_id

    cur = conn.execute(
        """
        INSERT INTO analysis_runs (
            person_id, cedula, folder_path, report_path, report_markdown, finca_count,
            alert_count, output_counts_json, ran_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            person_id,
            cedula,
            str(folder),
            str(report_path) if report_path else None,
            report_text,
            finca_count,
            alert_count,
            safe_json(counts),
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    return cur.lastrowid


def clear_run_details(conn, run_id):
    conn.execute('DELETE FROM alerts WHERE run_id = ?', (run_id,))
    conn.execute('DELETE FROM source_files WHERE run_id = ?', (run_id,))
    conn.execute('DELETE FROM movable_assets WHERE run_id = ?', (run_id,))
    conn.execute(
        'DELETE FROM finca_query_outputs WHERE query_output_id IN (SELECT id FROM query_outputs WHERE run_id = ?)',
        (run_id,),
    )
    conn.execute(
        'DELETE FROM finca_query_outputs WHERE finca_id IN (SELECT id FROM fincas WHERE run_id = ?)',
        (run_id,),
    )
    conn.execute('DELETE FROM query_outputs WHERE run_id = ?', (run_id,))
    conn.execute('DELETE FROM fincas WHERE run_id = ?', (run_id,))


def insert_fincas(conn, run_id, folder, finca_records, timestamp):
    inserted = []
    for order, record in enumerate(finca_records, 1):
        resumen = record['resumen']
        detalle = record['detalle']
        index_no = resumen.get('index') or order
        cur = conn.execute(
            """
            INSERT INTO fincas (
                run_id, index_no, provincia, provincia_codigo, numero, derecho, duplicado,
                horizontal, matricula, naturaleza, ubicacion, zona_catastrada, medida,
                plano, antecedentes, identificador_predial, valor_fiscal_text,
                valor_fiscal_num, propietario, anotaciones, gravamenes, resumen_json,
                detalle_json, texto, source_json, source_txt, source_html, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                index_no,
                resumen.get('provincia') or detalle.get('provincia'),
                province_code(resumen),
                str(resumen.get('numero') or detalle.get('finca') or ''),
                str(resumen.get('derecho') or detalle.get('derecho') or ''),
                str(resumen.get('duplicado') or detalle.get('duplicado') or ''),
                str(resumen.get('horizontal') or detalle.get('horizontal') or ''),
                detalle.get('matricula'),
                detalle.get('naturaleza'),
                detalle.get('ubicacion'),
                detalle.get('zona_catastrada'),
                detalle.get('medida'),
                detalle.get('plano'),
                detalle.get('antecedentes'),
                detalle.get('identificador_predial'),
                detalle.get('valor_fiscal'),
                money_number(detalle.get('valor_fiscal') or ''),
                detalle.get('propietario'),
                detalle.get('anotaciones'),
                detalle.get('gravamenes'),
                safe_json(resumen),
                safe_json(detalle),
                detalle.get('texto'),
                rel_path(record['path'], folder),
                rel_path(record['txt_path'], folder),
                rel_path(record['html_path'], folder),
                timestamp,
            ),
        )
        record['db_id'] = cur.lastrowid
        inserted.append(record)
    return inserted


def first_value(*values, default=None):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def insert_movable_assets(conn, run_id, folder, asset_records, timestamp):
    inserted = []
    for order, record in enumerate(asset_records, 1):
        resumen = record['resumen']
        detalle = record['detalle']
        numero = first_value(
            resumen.get('numero'),
            detalle.get('placa'),
            detalle.get('matricula'),
            detalle.get('serie'),
            detalle.get('vin'),
            detalle.get('motor'),
            resumen.get('identificacion'),
        )
        cur = conn.execute(
            """
            INSERT INTO movable_assets (
                run_id, index_no, asset_type, identificacion, nombre, tipo, numero,
                placa, matricula, marca, modelo, year, color, serie, vin, motor,
                chasis, propietario, cedula_propietario, estado, anotaciones,
                gravamenes, resumen_json, detalle_json, texto, source_json,
                source_txt, source_html, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                resumen.get('index') or order,
                'bien_mueble',
                resumen.get('identificacion'),
                resumen.get('nombre'),
                first_value(resumen.get('tipo'), detalle.get('tipo'), detalle.get('categoria'), default='bien_mueble'),
                numero,
                detalle.get('placa'),
                detalle.get('matricula'),
                detalle.get('marca'),
                first_value(detalle.get('modelo'), detalle.get('estilo')),
                first_value(detalle.get('year'), detalle.get('anio')),
                detalle.get('color'),
                detalle.get('serie'),
                detalle.get('vin'),
                detalle.get('motor'),
                detalle.get('chasis'),
                detalle.get('propietario'),
                detalle.get('cedula_propietario'),
                first_value(resumen.get('estado'), detalle.get('estado')),
                detalle.get('anotaciones'),
                detalle.get('gravamenes'),
                safe_json(resumen),
                safe_json(detalle),
                detalle.get('texto'),
                rel_path(record['path'], folder),
                rel_path(record['txt_path'], folder),
                rel_path(record['html_path'], folder),
                timestamp,
            ),
        )
        record['db_id'] = cur.lastrowid
        inserted.append(record)
    return inserted


def insert_source_files(conn, run_id, folder, timestamp):
    inserted = 0
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.json', '.txt', '.html', '.md'}:
            continue
        try:
            raw = path.read_bytes()
            content = raw.decode('utf-8', errors='replace')
        except OSError:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO source_files (
                run_id, relative_path, file_type, size_bytes, sha256, content_text, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                rel_path(path, folder),
                path.suffix.lower().lstrip('.'),
                len(raw),
                hashlib.sha256(raw).hexdigest(),
                content,
                timestamp,
            ),
        )
        inserted += 1
    return inserted


def matching_fincas(query_type, lookup_key, finca_records):
    matches = []
    for record in finca_records:
        resumen = record['resumen']
        detalle = record['detalle']
        text = detalle.get('texto') or ''
        if query_type == 'catastro_plano' and detalle.get('plano') == lookup_key:
            matches.append((record, 'plano'))
        elif query_type == 'finca_numero' and lookup_key == finca_stem(resumen):
            matches.append((record, 'finca'))
        elif query_type == 'historia_finca' and finca_stem(resumen) == lookup_key:
            matches.append((record, 'finca'))
        elif query_type == 'gravamen_hipoteca' and lookup_key in extract_citas(text):
            matches.append((record, 'cita'))
        elif query_type == 'documento_diario' and lookup_key in extract_presentaciones(text):
            matches.append((record, 'presentacion'))
        elif query_type == 'diario_defectos' and lookup_key in extract_presentaciones(text):
            matches.append((record, 'presentacion'))
        elif query_type == 'primeras_presentaciones':
            matches.append((record, 'persona'))
        elif query_type == 'anotaciones_tramites' and lookup_key in extract_presentaciones(text):
            matches.append((record, 'presentacion'))
        elif query_type == 'valores_finca' and lookup_key.startswith(f"{province_code(resumen)}_{resumen.get('numero', '')}"):
            matches.append((record, 'finca'))
        elif query_type == 'historia_gravamenes_inmuebles' and lookup_key in extract_citas(text):
            matches.append((record, 'cita'))
    return matches


def insert_query_outputs(conn, run_id, folder, finca_records, timestamp):
    inserted = 0
    for subdir, query_type in QUERY_DIRS.items():
        target = folder / subdir
        if not target.exists():
            continue
        for json_path in sorted(target.glob('*.json')):
            try:
                payload = load_json(json_path)
            except (json.JSONDecodeError, OSError):
                payload = {}
            lookup_key = json_path.stem
            txt_path = sibling(json_path, '.txt')
            html_path = sibling(json_path, '.html')
            cur = conn.execute(
                """
                INSERT INTO query_outputs (
                    run_id, query_type, lookup_key, consulta, entrada_json, origen_json,
                    payload_json, texto, source_json, source_txt, source_html, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    query_type,
                    lookup_key,
                    payload.get('consulta') if isinstance(payload, dict) else None,
                    safe_json(payload.get('entrada')) if isinstance(payload, dict) else None,
                    safe_json(payload.get('origen')) if isinstance(payload, dict) else None,
                    safe_json(payload),
                    payload.get('texto') if isinstance(payload, dict) else None,
                    rel_path(json_path, folder),
                    rel_path(txt_path, folder),
                    rel_path(html_path, folder),
                    timestamp,
                ),
            )
            query_id = cur.lastrowid
            inserted += 1
            for record, relation in matching_fincas(query_type, lookup_key, finca_records):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO finca_query_outputs (finca_id, query_output_id, relation)
                    VALUES (?, ?, ?)
                    """,
                    (record['db_id'], query_id, relation),
                )
    return inserted


def insert_alerts(conn, run_id, folder, finca_records, timestamp):
    flags = risk_flags(finca_records, folder)
    for record, label, severity, message, source in flags:
        conn.execute(
            """
            INSERT INTO alerts (run_id, finca_id, severity, label, message, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, record.get('db_id'), severity, label, message, source, timestamp),
        )
    return len(flags)


def ingest_folder(db_path, folder_path, cedula=None):
    folder = Path(folder_path).resolve()
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f'No existe la carpeta de análisis: {folder}')

    report_path = folder / 'analisis.md'
    report_text = safe_read_text(report_path)
    cedula = cedula_digits(cedula) or extract_cedula(folder, report_text)
    if not cedula:
        raise SystemExit('No pude detectar la cédula. Usa --cedula.')

    finca_records = load_fincas(folder)
    movable_records = load_movable_assets(folder)
    if not finca_records and not movable_records:
        raise SystemExit(f'No encontré JSONs de finca ni bienes muebles en: {folder}')

    owner = (
        (finca_records[0]['detalle'].get('propietario') if finca_records else None)
        or (movable_records[0]['detalle'].get('propietario') if movable_records else None)
        or (movable_records[0]['resumen'].get('nombre') if movable_records else None)
    )
    first_name = extract_first_name(folder, cedula)
    counts = output_counts(folder)
    parsed_counts = parse_report_counts(report_text)
    computed_alerts = len(risk_flags(finca_records, folder))
    finca_count = parsed_counts.get('finca_count', len(finca_records))
    alert_count = parsed_counts.get('alert_count', computed_alerts)
    timestamp = now_iso()

    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        init_db(conn)
        person_id = upsert_person(conn, cedula, owner, first_name, folder, timestamp)
        run_id = upsert_run(
            conn,
            person_id,
            cedula,
            folder,
            report_path if report_path.exists() else None,
            report_text,
            finca_count,
            alert_count,
            counts,
            timestamp,
        )
        clear_run_details(conn, run_id)
        inserted_fincas = insert_fincas(conn, run_id, folder, finca_records, timestamp)
        inserted_assets = insert_movable_assets(conn, run_id, folder, movable_records, timestamp)
        output_count = insert_query_outputs(conn, run_id, folder, inserted_fincas, timestamp)
        source_file_count = insert_source_files(conn, run_id, folder, timestamp)
        inserted_alerts = insert_alerts(conn, run_id, folder, inserted_fincas, timestamp)
        if inserted_alerts != alert_count:
            conn.execute(
                'UPDATE analysis_runs SET alert_count = ?, updated_at = ? WHERE id = ?',
                (inserted_alerts, timestamp, run_id),
            )
            alert_count = inserted_alerts

    return {
        'db_path': str(db_path),
        'person': owner or first_name or cedula,
        'cedula': cedula,
        'folder': str(folder),
        'run_id': run_id,
        'finca_count': len(finca_records),
        'movable_asset_count': len(inserted_assets),
        'query_output_count': output_count,
        'source_file_count': source_file_count,
        'alert_count': alert_count,
    }


def latest_run_for_person(conn, cedula):
    return conn.execute(
        """
        SELECT ar.*, p.nombre, p.first_name
        FROM analysis_runs ar
        JOIN persons p ON p.id = ar.person_id
        WHERE p.cedula = ?
        ORDER BY ar.updated_at DESC, ar.id DESC
        LIMIT 1
        """,
        (cedula,),
    ).fetchone()


def cmd_init(args):
    with connect(Path(args.db).resolve()) as conn:
        init_db(conn)
    print(f'Base de datos lista: {Path(args.db).resolve()}')


def cmd_ingest(args):
    result = ingest_folder(args.db, args.folder, cedula=args.cedula)
    print(
        'Guardado en base de datos: '
        f"{result['person']} ({result['cedula']}) | "
        f"fincas={result['finca_count']} | "
        f"bienes_muebles={result['movable_asset_count']} | "
        f"consultas_extra={result['query_output_count']} | "
        f"archivos={result['source_file_count']} | "
        f"alertas={result['alert_count']} | "
        f"db={result['db_path']}"
    )


def cmd_list(args):
    db_path = Path(args.db).resolve()
    with connect(db_path) as conn:
        init_db(conn)
        rows = conn.execute(
            """
            SELECT
                p.cedula,
                COALESCE(p.nombre, p.first_name, '') AS nombre,
                ar.finca_count,
                ar.alert_count,
                (
                    SELECT COUNT(*)
                    FROM movable_assets ma
                    WHERE ma.run_id = ar.id
                ) AS movable_asset_count,
                ar.updated_at,
                ar.folder_path
            FROM persons p
            LEFT JOIN analysis_runs ar ON ar.id = (
                SELECT id FROM analysis_runs
                WHERE person_id = p.id
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
            )
            ORDER BY p.updated_at DESC
            """
        ).fetchall()

    if args.json:
        print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
        return
    if not rows:
        print(f'No hay personas guardadas en {db_path}')
        return
    print('cedula      fincas  muebles  alertas  nombre')
    for row in rows:
        print(
            f"{row['cedula']:<11} {row['finca_count'] or 0:>6} "
            f"{row['movable_asset_count'] or 0:>7} {row['alert_count'] or 0:>8}  {row['nombre']}"
        )


def cmd_show(args):
    cedula = cedula_digits(args.cedula)
    if not cedula:
        raise SystemExit('La cédula no contiene dígitos.')
    db_path = Path(args.db).resolve()
    with connect(db_path) as conn:
        init_db(conn)
        run = latest_run_for_person(conn, cedula)
        if not run:
            raise SystemExit(f'No encontré datos para cédula {cedula} en {db_path}')
        fincas = conn.execute(
            """
            SELECT id, index_no, provincia, numero, derecho, plano, valor_fiscal_text, gravamenes, naturaleza
            FROM fincas
            WHERE run_id = ?
            ORDER BY index_no, id
            """,
            (run['id'],),
        ).fetchall()
        outputs = conn.execute(
            """
            SELECT query_type, COUNT(*) AS total
            FROM query_outputs
            WHERE run_id = ?
            GROUP BY query_type
            ORDER BY query_type
            """,
            (run['id'],),
        ).fetchall()
        alerts = conn.execute(
            """
            SELECT severity, label, message
            FROM alerts
            WHERE run_id = ?
            ORDER BY id
            """,
            (run['id'],),
        ).fetchall()
        movable_assets = conn.execute(
            """
            SELECT id, index_no, tipo, numero, placa, marca, modelo, year, serie, vin,
                   motor, chasis, propietario, estado, anotaciones, gravamenes
            FROM movable_assets
            WHERE run_id = ?
            ORDER BY index_no, id
            """,
            (run['id'],),
        ).fetchall()
        source_files = conn.execute(
            'SELECT COUNT(*) AS total FROM source_files WHERE run_id = ?',
            (run['id'],),
        ).fetchone()['total']

    if args.json:
        payload = {
            'persona': {
                'cedula': cedula,
                'nombre': run['nombre'],
                'first_name': run['first_name'],
            },
            'analisis': dict(run),
            'fincas': [dict(row) for row in fincas],
            'bienes_muebles': [dict(row) for row in movable_assets],
            'consultas_extra': [dict(row) for row in outputs],
            'alertas': [dict(row) for row in alerts],
            'source_files': source_files,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"Persona: {run['nombre'] or run['first_name'] or cedula}")
    print(f"Cédula: {cedula}")
    print(f"Carpeta: {run['folder_path']}")
    print(f"Reporte: {run['report_path'] or 'sin analisis.md'}")
    print(f"Fincas: {run['finca_count']} | Bienes muebles: {len(movable_assets)} | Alertas: {run['alert_count']}")
    print(f"Archivos crudos guardados: {source_files}")
    if outputs:
        print('Consultas extra: ' + ', '.join(f"{row['query_type']}={row['total']}" for row in outputs))
    print()
    print('Fincas:')
    for row in fincas:
        label = f"{row['provincia']} {row['numero']} derecho {row['derecho']}".strip()
        print(f"- {label} | plano={row['plano'] or '-'} | valor={row['valor_fiscal_text'] or '-'} | gravámenes={row['gravamenes'] or '-'}")
    if movable_assets:
        print()
        print('Bienes muebles:')
        for row in movable_assets:
            label = row['numero'] or row['placa'] or row['serie'] or row['vin'] or row['motor'] or '-'
            print(f"- {row['tipo'] or 'bien_mueble'} {label} | marca={row['marca'] or '-'} | modelo={row['modelo'] or '-'} | propietario={row['propietario'] or '-'}")
    if alerts:
        print()
        print('Alertas:')
        for row in alerts:
            print(f"- [{row['severity']}] {row['label']}: {row['message']}")


def build_parser():
    parser = argparse.ArgumentParser(description='Base de datos local para análisis RNP por cédula.')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Ruta SQLite. Default: {DEFAULT_DB}')
    sub = parser.add_subparsers(dest='command', required=True)

    p_init = sub.add_parser('init', help='Crear o actualizar el esquema SQLite')
    p_init.set_defaults(func=cmd_init)

    p_ingest = sub.add_parser('ingest', help='Guardar una carpeta de análisis RNP en SQLite')
    p_ingest.add_argument('folder', help='Carpeta con analisis.md y JSON/TXT/HTML generados')
    p_ingest.add_argument('--cedula', help='Cédula consultada; si se omite se extrae de la carpeta/reporte')
    p_ingest.set_defaults(func=cmd_ingest)

    p_list = sub.add_parser('list', help='Listar personas guardadas')
    p_list.add_argument('--json', action='store_true', help='Salida JSON')
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser('show', help='Mostrar el último análisis de una cédula')
    p_show.add_argument('cedula', help='Cédula a consultar')
    p_show.add_argument('--json', action='store_true', help='Salida JSON')
    p_show.set_defaults(func=cmd_show)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except sqlite3.Error as exc:
        raise SystemExit(f'Error SQLite: {exc}') from exc


if __name__ == '__main__':
    main()
