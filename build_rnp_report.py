#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


QUERY_SCRIPTS = [
    ("finca_numero", "rnp_finca_numero.py"),
    ("catastro_planos", "rnp_catastro_plano.py"),
    ("historia_fincas", "rnp_historia_finca.py"),
    ("gravamenes_hipotecas", "rnp_gravamen_hipoteca.py"),
    ("documentos_diario", "rnp_documento_diario.py"),
    ("diario_defectos", "rnp_diario_defectos.py"),
    ("primeras_presentaciones", "rnp_primeras_presentaciones.py"),
    ("anotaciones_tramites", "rnp_anotaciones_tramites.py"),
    ("valores_finca", "rnp_valores_finca.py"),
    ("historia_gravamenes_inmuebles", "rnp_historia_gravamenes_inmuebles.py"),
]

MUEBLE_QUERY_SCRIPTS = [
    ("historia_bienes_muebles", "rnp_historia_bienes_muebles.py"),
    ("historia_presentaciones_muebles", "rnp_historia_presentaciones_muebles.py"),
    ("citas_presentacion_muebles", "rnp_citas_presentacion_muebles.py"),
    ("gravamenes_bienes_muebles", "rnp_gravamenes_bienes_muebles.py"),
]


def run(cmd, cwd, timeout=None):
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if proc.stdout:
        print(proc.stdout, end='')
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(f'✗ Command failed ({proc.returncode}): {" ".join(cmd)}')
    return proc


def safe_name(value):
    return re.sub(r'[^0-9A-Za-z_.-]+', '_', str(value).strip()).strip('_') or 'rnp'


def cedula_digits(raw):
    digits = re.sub(r'\D', '', raw)
    if not digits:
        raise SystemExit('✗ La cédula no contiene dígitos.')
    return digits


def discover_folder(project, cedula, stdout=''):
    m = re.search(r'Guardando detalles de \d+ finca\(s\) en ([^\n.]+)', stdout)
    if m:
        path = project / m.group(1).strip()
        if path.exists():
            return path

    digits = cedula_digits(cedula)
    candidates = [p for p in project.iterdir() if p.is_dir() and p.name.endswith('_' + digits)]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)

    legacy = project / f'rnp_{digits}_fincas'
    if legacy.exists():
        return legacy

    raise SystemExit('✗ No pude detectar la carpeta de resultados generada por la consulta inicial.')


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def finca_files(folder):
    files = []
    for path in sorted(folder.glob('*.json')):
        data = load_json(path)
        if isinstance(data, dict) and 'resumen' in data and 'detalle' in data:
            files.append((path, data))
    return files


def mueble_files(folder):
    files = []
    target = folder / 'bienes_muebles'
    if not target.exists():
        return files
    for path in sorted(target.glob('*.json')):
        data = load_json(path)
        if isinstance(data, dict) and 'resumen' in data and 'detalle' in data:
            files.append((path, data))
    return files


def read_text(path):
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def money_number(value):
    m = re.search(r'([\d,.]+)', value or '')
    if not m:
        return None
    return float(m.group(1).replace(',', ''))


def extract_presentaciones(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{5,8}-\d{2}\b(?!-\d{4}-\d{3})', text or '')))


def extract_citas(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{4,8}-\d{2}-\d{4}-\d{3}\b', text or '')))


def output_exists(folder, subdir, stem):
    target_dir = folder / subdir
    if not target_dir.exists():
        return False
    return any(p.stem == stem for p in target_dir.glob('*.json'))


def province_code(summary):
    m = re.match(r'(\d+)', str(summary.get('provincia', '')).strip())
    if m:
        return m.group(1)
    params = summary.get('params') or {}
    return str(params.get('provincia') or summary.get('provincia_codigo') or '0')


def find_source(folder, subdir, stem):
    target_dir = folder / subdir
    for suffix in ('.txt', '.json', '.html'):
        path = target_dir / (safe_name(stem) + suffix)
        if path.exists():
            return path
    return None


def rel(path, root):
    return path.relative_to(root).as_posix()


def first_value(*values, default='-'):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def risk_flags(fincas, folder):
    flags = []
    for path, data in fincas:
        resumen = data.get('resumen', {})
        detalle = data.get('detalle', {})
        label = f'{resumen.get("provincia", "")} {resumen.get("numero", "")}'.strip()
        text = detalle.get('texto', '')

        grav = (detalle.get('gravamenes') or '').strip().upper()
        if grav and grav != 'NO HAY':
            flags.append((label, f'Gravámenes/afectaciones reportadas: {detalle.get("gravamenes")}'))

        for term in ('HIPOTECA', 'SERVIDUMBRE', 'CONDIC', 'RESERV', 'LIMITACIONES', 'HABITACION FAMILIAR'):
            if term in text.upper():
                flags.append((label, f'El texto contiene indicador registral: {term}'))

        value = money_number(detalle.get('valor_fiscal', ''))
        if value is not None and value <= 1:
            flags.append((label, f'Valor fiscal sospechosamente bajo: {detalle.get("valor_fiscal")}'))

        if detalle.get('plano') and not output_exists(folder, 'catastro_planos', detalle['plano']):
            flags.append((label, f'Falta salida de catastro para plano {detalle["plano"]}'))

        hist_stem = f'{province_code(resumen)}_{resumen.get("numero")}_{resumen.get("derecho")}'
        if not output_exists(folder, 'historia_fincas', hist_stem):
            flags.append((label, 'Falta salida de historia de finca'))

        for presentacion in extract_presentaciones(text):
            if not output_exists(folder, 'documentos_diario', presentacion):
                flags.append((label, f'Falta salida de Diario para presentación {presentacion}'))

    return flags


def make_markdown(folder, cedula, out_path):
    fincas = finca_files(folder)
    muebles = mueble_files(folder)

    if not fincas and not muebles:
        owner = folder.name.split('_')[0] or cedula
        out_path.write_text(
            '\n'.join([
                f'# Análisis RNP - {owner}',
                '',
                f'- Cédula consultada: `{cedula}`',
                f'- Carpeta fuente: `{folder}`',
                '- Fincas encontradas: `0`',
                '- Bienes muebles encontrados: `0`',
                '- Alertas automáticas: `0`',
                '',
                '## Resumen Ejecutivo',
                '',
                'No se encontraron bienes inmuebles (fincas) ni bienes muebles registrados a nombre de esta cédula en el RNP.',
                '',
                '## Detalle',
                '',
                'La consulta se completó sin errores pero el RNP no devolvió registros de propiedades para esta persona.',
                '',
            ]),
            encoding='utf-8',
        )
        return out_path

    first = fincas[0][1] if fincas else muebles[0][1]
    owner = (
        first.get('detalle', {}).get('propietario')
        or first.get('resumen', {}).get('nombre')
        or folder.name.split('_')[0]
    )
    flags = risk_flags(fincas, folder)

    lines = [
        f'# Análisis RNP - {owner}',
        '',
        f'- Cédula consultada: `{cedula}`',
        f'- Carpeta fuente: `{folder}`',
        f'- Fincas encontradas: `{len(fincas)}`',
        f'- Bienes muebles encontrados: `{len(muebles)}`',
        f'- Alertas automáticas: `{len(flags)}`',
        '',
        '## Resumen Ejecutivo',
        '',
    ]

    if flags:
        lines.append('Se detectaron elementos que ameritan revisión:')
        for label, msg in flags[:20]:
            lines.append(f'- **{label}**: {msg}')
        if len(flags) > 20:
            lines.append(f'- Hay {len(flags) - 20} alertas adicionales en los detalles por finca.')
    else:
        lines.append('No se detectaron alertas automáticas relevantes en los campos analizados.')

    if fincas:
        lines.extend([
            '',
            '## Inventario de Fincas',
            '',
            '| # | Finca | Naturaleza | Plano | Valor fiscal | Gravámenes |',
            '|---:|---|---|---|---:|---|',
        ])

        for idx, (path, data) in enumerate(fincas, 1):
            resumen = data.get('resumen', {})
            detalle = data.get('detalle', {})
            finca_label = f'{resumen.get("provincia", "")} {resumen.get("numero", "")} derecho {resumen.get("derecho", "")}'
            lines.append(
                f'| {idx} | {finca_label} | {detalle.get("naturaleza", "-")} | '
                f'{detalle.get("plano", "-")} | {detalle.get("valor_fiscal", "-")} | {detalle.get("gravamenes", "-")} |'
            )

    if muebles:
        lines.extend([
            '',
            '## Inventario de Bienes Muebles',
            '',
            '| # | Identificación/Número | Marca | Modelo | Placa/Serie/VIN | Estado | Gravámenes |',
            '|---:|---|---|---|---|---|---|',
        ])
        for idx, (path, data) in enumerate(muebles, 1):
            resumen = data.get('resumen', {})
            detalle = data.get('detalle', {})
            numero = first_value(
                resumen.get('numero'),
                detalle.get('placa'),
                detalle.get('matricula'),
                detalle.get('serie'),
                detalle.get('vin'),
                resumen.get('identificacion'),
            )
            ids = ' / '.join(
                value for value in [
                    detalle.get('placa'),
                    detalle.get('serie'),
                    detalle.get('vin'),
                ] if value
            ) or '-'
            lines.append(
                f'| {idx} | {numero} | {first_value(detalle.get("marca"))} | '
                f'{first_value(detalle.get("modelo"), detalle.get("estilo"))} | {ids} | '
                f'{first_value(resumen.get("estado"), detalle.get("estado"))} | '
                f'{first_value(detalle.get("gravamenes"), detalle.get("anotaciones"))} |'
            )

    if fincas:
        lines.extend(['', '## Detalle por Finca', ''])
        for idx, (path, data) in enumerate(fincas, 1):
            resumen = data.get('resumen', {})
            detalle = data.get('detalle', {})
            label = f'{resumen.get("provincia", "")} {resumen.get("numero", "")} derecho {resumen.get("derecho", "")}'
            txt_path = path.with_suffix('.txt')
            source_line = f'[{rel(txt_path, folder)}]({rel(txt_path, folder)})' if txt_path.exists() else '-'
            lines.extend([
                f'### {idx}. {label}',
                '',
                f'- Naturaleza: {detalle.get("naturaleza", "-")}',
                f'- Ubicación: {detalle.get("ubicacion", "-")}',
                f'- Medida: {detalle.get("medida", "-")}',
                f'- Plano: {detalle.get("plano", "-")}',
                f'- Identificador predial: {detalle.get("identificador_predial", "-")}',
                f'- Valor fiscal: {detalle.get("valor_fiscal", "-")}',
                f'- Propietario: {detalle.get("propietario", "-")}',
                f'- Anotaciones: {detalle.get("anotaciones", "-")}',
                f'- Gravámenes/afectaciones: {detalle.get("gravamenes", "-")}',
                f'- Fuente finca: {source_line}',
            ])

            plano = detalle.get('plano')
            if plano:
                source = find_source(folder, 'catastro_planos', plano)
                lines.append(f'- Catastro por plano: {("[{}]({})".format(rel(source, folder), rel(source, folder)) if source else "pendiente")}')

            hist_stem = f'{province_code(resumen)}_{resumen.get("numero")}_{resumen.get("derecho")}'
            hist = find_source(folder, 'historia_fincas', hist_stem)
            lines.append(f'- Historia de finca: {("[{}]({})".format(rel(hist, folder), rel(hist, folder)) if hist else "pendiente")}')

            presentaciones = extract_presentaciones(detalle.get('texto', ''))
            if presentaciones:
                lines.append('- Presentaciones/Diario:')
                for pres in presentaciones:
                    source = find_source(folder, 'documentos_diario', pres)
                    lines.append(f'  - `{pres}`: {("[{}]({})".format(rel(source, folder), rel(source, folder)) if source else "pendiente")}')

            citas = extract_citas(detalle.get('texto', ''))
            if citas:
                lines.append('- Citas de gravámenes/hipotecas:')
                for cita in citas:
                    source = find_source(folder, 'gravamenes_hipotecas', cita)
                    lines.append(f'  - `{cita}`: {("[{}]({})".format(rel(source, folder), rel(source, folder)) if source else "pendiente")}')
            lines.append('')

    if muebles:
        lines.extend(['', '## Detalle de Bienes Muebles', ''])
        for idx, (path, data) in enumerate(muebles, 1):
            resumen = data.get('resumen', {})
            detalle = data.get('detalle', {})
            numero = first_value(
                resumen.get('numero'),
                detalle.get('placa'),
                detalle.get('matricula'),
                detalle.get('serie'),
                detalle.get('vin'),
                resumen.get('identificacion'),
            )
            txt_path = path.with_suffix('.txt')
            source_line = f'[{rel(txt_path, folder)}]({rel(txt_path, folder)})' if txt_path.exists() else '-'
            lines.extend([
                f'### {idx}. {first_value(resumen.get("tipo"), detalle.get("tipo"), detalle.get("categoria"))} {numero}',
                '',
                f'- Identificación resumen: {first_value(resumen.get("identificacion"))}',
                f'- Nombre resumen: {first_value(resumen.get("nombre"))}',
                f'- Placa: {first_value(detalle.get("placa"))}',
                f'- Marca: {first_value(detalle.get("marca"))}',
                f'- Modelo/estilo: {first_value(detalle.get("modelo"), detalle.get("estilo"))}',
                f'- Año: {first_value(detalle.get("year"), detalle.get("anio"))}',
                f'- Color: {first_value(detalle.get("color"))}',
                f'- Serie: {first_value(detalle.get("serie"))}',
                f'- VIN: {first_value(detalle.get("vin"))}',
                f'- Motor: {first_value(detalle.get("motor"))}',
                f'- Chasis: {first_value(detalle.get("chasis"))}',
                f'- Propietario: {first_value(detalle.get("propietario"))}',
                f'- Anotaciones: {first_value(detalle.get("anotaciones"))}',
                f'- Gravámenes/afectaciones: {first_value(detalle.get("gravamenes"))}',
                f'- Fuente bien mueble: {source_line}',
                '',
            ])

    lines.extend([
        '## Limitaciones',
        '',
        '- Este es un análisis automático de información consultada en RNP Digital.',
        '- No sustituye una revisión legal, notarial, registral ni catastral profesional.',
        '- La ausencia de una alerta automática no garantiza ausencia de riesgos.',
        '- Revisar siempre los HTML/TXT fuente antes de tomar decisiones.',
        '',
    ])

    out_path.write_text('\n'.join(lines), encoding='utf-8')
    return out_path


def id_type_for_cedula(cedula):
    digits = cedula_digits(cedula)
    if len(digits) == 9:
        return 'fisica'
    if len(digits) in (10, 11):
        return 'juridica'
    return 'fisica'


def fetch_muebles(project, cedula, folder, pausa):
    script = project / 'rnp_persona_bienes_muebles.py'
    if not script.exists():
        print('! rnp_persona_bienes_muebles.py not found; Bienes Muebles skipped', file=sys.stderr)
        return
    cmd = [
        sys.executable,
        'rnp_persona_bienes_muebles.py',
        cedula,
        '--tipo',
        id_type_for_cedula(cedula),
        '--salida',
        str(folder / 'bienes_muebles'),
    ]
    run(cmd, cwd=project, timeout=None)
    if pausa:
        time.sleep(pausa)


def fetch_mueble_aux(project, folder, pausa, limite):
    for _, script in MUEBLE_QUERY_SCRIPTS:
        path = project / script
        if not path.exists():
            print(f'! {script} not found; movable auxiliary query skipped', file=sys.stderr)
            continue
        cmd = [sys.executable, script, '--desde-carpeta', str(folder)]
        if limite is not None:
            cmd += ['--limite', str(limite)]
        if pausa:
            cmd += ['--pausa', str(pausa)]
        run(cmd, cwd=project, timeout=None)
        if pausa:
            time.sleep(pausa)


def fetch_all(project, cedula, pausa, limite, include_muebles=True):
    initial = run([sys.executable, 'rnp_persona_bienes_inmuebles.py', cedula], cwd=project, timeout=None)
    folder = discover_folder(project, cedula, initial.stdout)

    for _, script in QUERY_SCRIPTS:
        cmd = [sys.executable, script, '--desde-carpeta', str(folder)]
        if limite is not None:
            cmd += ['--limite', str(limite)]
        if pausa:
            cmd += ['--pausa', str(pausa)]
        run(cmd, cwd=project, timeout=None)
        if pausa:
            time.sleep(pausa)
    if include_muebles:
        fetch_muebles(project, cedula, folder, pausa)
        fetch_mueble_aux(project, folder, pausa, limite)
    return folder


def resolve_project_path(project, value):
    path = Path(value)
    return path if path.is_absolute() else project / path


def save_database(project, folder, cedula, db_path, user_id=None):
    if db_path in ('postgresql', 'pg'):
        pg_script = project / 'backend' / 'rnp_ingest_pg.py'
        if not pg_script.exists():
            pg_script = project / 'rnp_ingest_pg.py'
        if not pg_script.exists():
            print('! rnp_ingest_pg.py not found; PostgreSQL ingest skipped', file=sys.stderr)
            return None
        cmd = [
            sys.executable,
            str(pg_script),
            str(folder),
            '--cedula',
            cedula,
        ]
        if user_id is not None:
            cmd += ['--user-id', str(user_id)]
        run(cmd, cwd=project, timeout=None)
        return 'postgresql'

    db_script = project / 'rnp_database.py'
    if not db_script.exists():
        print('! rnp_database.py not found; SQLite ingest skipped', file=sys.stderr)
        return None

    resolved_db = resolve_project_path(project, db_path or 'rnp_personas.sqlite').resolve()
    run(
        [
            sys.executable,
            str(db_script),
            '--db',
            str(resolved_db),
            'ingest',
            str(folder),
            '--cedula',
            cedula,
        ],
        cwd=project,
        timeout=None,
    )
    return resolved_db


def main():
    ap = argparse.ArgumentParser(description='Collect RNP data from a cédula and write a Markdown analysis.')
    ap.add_argument('cedula', help='Cédula física or jurídica used as the initial input')
    ap.add_argument('--project', default='.', help='RNP automation project directory')
    ap.add_argument('--folder', help='Existing collected output folder')
    ap.add_argument('--no-fetch', action='store_true', help='Only generate analysis from --folder')
    ap.add_argument('--output', help='Markdown output path; default: <folder>/analisis.md')
    ap.add_argument('--db', help='SQLite output path; default: <project>/rnp_personas.sqlite')
    ap.add_argument('--no-db', action='store_true', help='Skip SQLite ingest after writing the Markdown report')
    ap.add_argument('--no-muebles', action='store_true', help='Skip Bienes Muebles by identification')
    ap.add_argument('--pausa', type=float, default=15.0, help='Seconds between batch queries')
    ap.add_argument('--limite', type=int, help='Limit records per auxiliary query script, useful for tests')
    ap.add_argument('--user-id', type=int, help='User ID for ownership (passed to ingest)')
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        raise SystemExit(f'✗ Project directory does not exist: {project}')

    if args.no_fetch:
        if not args.folder:
            raise SystemExit('✗ --no-fetch requires --folder')
        folder = (project / args.folder).resolve()
    else:
        required = [('persona', 'rnp_persona_bienes_inmuebles.py'), *QUERY_SCRIPTS]
        if not args.no_muebles:
            required.append(('bienes_muebles', 'rnp_persona_bienes_muebles.py'))
            required.extend(MUEBLE_QUERY_SCRIPTS)
        for _, script in required:
            if not (project / script).exists():
                raise SystemExit(f'✗ Required script missing in project: {script}')
        folder = fetch_all(project, args.cedula, args.pausa, args.limite, include_muebles=not args.no_muebles)

    if not folder.exists():
        raise SystemExit(f'✗ Results folder does not exist: {folder}')

    output = Path(args.output).resolve() if args.output else folder / 'analisis.md'
    report = make_markdown(folder, args.cedula, output)
    print(f'✓ Markdown analysis written: {report}')
    if not args.no_db:
        if not finca_files(folder) and not mueble_files(folder):
            print('! No records to ingest; SQLite database skipped', file=sys.stderr)
        else:
            db_path = save_database(project, folder, args.cedula, args.db, user_id=args.user_id)
            if db_path:
                print(f'✓ SQLite database updated: {db_path}')


if __name__ == '__main__':
    main()
