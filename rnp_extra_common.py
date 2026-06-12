import argparse
import getpass
import html
import json
import os
import re
import sys
import time

from rnp_indice_documentos import BASE, INDEX_PATH, RNP, load_dotenv, parse_options


def clean(s):
    s = re.sub(r'<script\b[^>]*>.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<style\b[^>]*>.*?</style>', ' ', s, flags=re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def safe_name(value):
    value = re.sub(r'[^0-9A-Za-z_.-]+', '_', str(value).strip())
    return value.strip('_') or 'resultado'


def parse_jsf_params(pvp):
    parts = pvp.split(',')
    return dict(zip(parts[0::2], parts[1::2]))


def add_auth_args(ap):
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')


def login_from_args(args):
    load_dotenv()
    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')
    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    return rnp


def open_free_query(rnp, section, text):
    _, index = rnp.indice()
    options = parse_options(index)
    selected = next((o for o in options if o['section'] == section and o['text'] == text), None)
    if not selected:
        raise SystemExit(f'✗ No encontré la consulta: {section} - {text}')

    data = {
        selected['form']: selected['form'],
        'javax.faces.ViewState': rnp._viewstate(index),
    }
    data.update(selected['params'])
    return rnp._req(rnp._abs(selected['action']), data, ref=BASE + INDEX_PATH)


def form_action_url(rnp, h, form_id):
    m = re.search(
        r'<form[^>]*id="' + re.escape(form_id) + r'"[^>]*action="([^"]*)"',
        h,
        re.S)
    if not m:
        raise SystemExit(f'✗ No encontré el action del formulario {form_id}.')
    return rnp._abs(m.group(1))


def extract_tables(h):
    tables = []
    for table in re.findall(r'<table\b[^>]*>(.*?)</table>', h, re.S | re.I):
        rows = []
        for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table, re.S | re.I):
            cells = [clean(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def save_outputs(out_dir, base_name, html_body, payload):
    os.makedirs(out_dir, exist_ok=True)
    base = safe_name(base_name)
    html_path = os.path.join(out_dir, base + '.html')
    txt_path = os.path.join(out_dir, base + '.txt')
    json_path = os.path.join(out_dir, base + '.json')

    text = clean(html_body)
    data = dict(payload)
    data['texto'] = text
    data['tablas'] = extract_tables(html_body)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_body)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text.rstrip() + '\n')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return txt_path, json_path, html_path


def finca_records_from_dir(folder):
    records = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(folder, name)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if 'resumen' in data and 'detalle' in data:
            data['_path'] = path
            records.append(data)
    return records


def limit_records(records, limit):
    return records if limit is None else records[:limit]


def maybe_pause(seconds):
    if seconds and seconds > 0:
        time.sleep(seconds)


def add_batch_args(ap):
    ap.add_argument('--desde-carpeta', metavar='DIR',
                    help='Lee fincas guardadas por rnp_persona_bienes_inmuebles.py')
    ap.add_argument('--salida', metavar='DIR', help='Carpeta de salida')
    ap.add_argument('--limite', type=int, help='Procesa solo los primeros N resultados')
    ap.add_argument('--pausa', type=float, default=0.0,
                    help='Segundos de espera entre consultas en modo lote')


def require_direct_or_folder(args, direct_value_name):
    if getattr(args, direct_value_name) is None and not args.desde_carpeta:
        raise SystemExit(f'✗ Indique {direct_value_name.replace("_", " ")} o use --desde-carpeta DIR.')


def province_code_from_summary(summary):
    provincia = str(summary.get('provincia', '')).strip()
    m = re.match(r'(\d+)', provincia)
    if m:
        return m.group(1)
    return str(summary.get('provincia_codigo', '')).strip()


def derecho_from_summary(summary):
    derecho = str(summary.get('derecho', '')).strip()
    return derecho.zfill(3) if derecho.isdigit() else derecho
