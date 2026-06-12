#!/usr/bin/env python3
"""
Consulta de Aeronaves por Numero de Serie o Matricula en el Registro Nacional.

Uso:
    python3 rnp_aeronaves.py --serie N12345
    python3 rnp_aeronaves.py --matricula YR1234
    python3 rnp_aeronaves.py --serie N12345 --salida aeronaves
    python3 rnp_aeronaves.py --serie N12345 --no-guardar
    RNP_USER=correo@x.com RNP_PASS=MiClave python3 rnp_aeronaves.py --serie N12345

Credenciales (orden de prioridad): --user/--pass > .env > $RNP_USER/$RNP_PASS > prompt.
"""
import argparse
import getpass
import html
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
import http.cookiejar

UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36')
BASE = 'https://www.rnpdigital.com/shopping/'
ROOT = 'https://www.rnpdigital.com'
INDEX_PATH = 'consultaDocumentos/indiceDocumentos.jspx'
FORM_PATH = 'consultaDocumentos/bienesMuebles/paramConsultaAeronaves.jspx'

TIPOS_BUSQUEDA = {
    'serie': 'SER',
    'matricula': 'PLA',
}


class RNP:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def _req(self, url, data=None, ref=None, ajax=False):
        h = {'User-Agent': UA, 'Accept-Language': 'es-CR,es;q=0.9,en;q=0.8'}
        h['Accept'] = 'text/xml,*/*' if ajax else 'text/html,application/xhtml+xml,*/*;q=0.8'
        if ajax:
            h['X-Requested-With'] = 'XMLHttpRequest'
        if ref:
            h['Referer'] = ref
        body = None
        if data is not None:
            h['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            body = urllib.parse.urlencode(data).encode()
        r = self.op.open(urllib.request.Request(url, data=body, headers=h), timeout=40)
        return r.geturl(), r.read().decode('utf-8', 'replace')

    @staticmethod
    def _viewstate(h):
        m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', h)
        return m.group(1) if m else None

    @staticmethod
    def _form(h, needle):
        for m in re.finditer(r'<form[^>]*id="([^"]*)"[^>]*action="([^"]*)"[^>]*>(.*?)</form>', h, re.S):
            if needle in m.group(3):
                return m.group(1), m.group(2), m.group(3)
        return None

    @staticmethod
    def _inputs(body):
        out = {}
        for inp in re.finditer(r'<input\b[^>]*>', body):
            t = inp.group(0)
            nm = re.search(r'name="([^"]*)"', t)
            if not nm:
                continue
            vl = re.search(r'value="([^"]*)"', t)
            tp = re.search(r'type="([^"]*)"', t)
            out[nm.group(1)] = {'val': html.unescape(vl.group(1)) if vl else '',
                                'type': tp.group(1) if tp else ''}
        return out

    @staticmethod
    def _abs(action):
        return ROOT + action if action.startswith('/') else BASE + action

    def login(self, email, password):
        _, h = self._req(BASE + 'login.jspx')
        fid, act, body = self._form(h, 'type="password"')
        fields = self._inputs(body)
        vs = self._viewstate(h)
        action = self._abs(act)

        common = {fid: fid, fid + ':correo': email, fid + ':pass': password,
                  'javax.faces.ViewState': vs}
        for n, meta in fields.items():
            if meta['type'] == 'hidden' and n not in common:
                common[n] = meta['val']

        btn = next((n for n in fields if re.fullmatch(re.escape(fid) + r':j_id\d+', n)
                    and fields[n]['type'] == 'button'), fid + ':j_id26')
        d = dict(common)
        d['AJAXREQUEST'] = fid
        d[btn] = btn
        _, lh = self._req(action, d, ref=BASE + 'login.jspx', ajax=True)

        if 'incorrect' in lh.lower() or 'no es correc' in lh.lower():
            raise SystemExit('✗ Credenciales incorrectas según el RNP.')

        if 'modalSesionActiva' in lh:
            mfid, mact, mbody = self._form(h, 'continuar')
            mf = self._inputs(mbody)
            si = next(n for n, mt in mf.items()
                      if mt['type'] == 'submit' and 'continuar' in mt['val'].lower())
            d = {mfid: mfid, si: mf[si]['val'], 'javax.faces.ViewState': self._viewstate(h)}
            self._req(self._abs(mact), d, ref=BASE + 'login.jspx')

    def open_aeronave_form(self):
        index_url = BASE + INDEX_PATH
        _, h = self._req(index_url, ref=BASE + 'login.jspx')
        vs = self._viewstate(h)
        link = find_aeronave_link(h)
        if not vs or not link:
            raise SystemExit('✗ No se encontró la opción de Consulta de Aeronaves.')
        data = {
            link['form']: link['form'],
            'javax.faces.ViewState': vs,
        }
        data.update(link['params'])
        _, form = self._req(self._abs(link['action']), data, ref=index_url)
        if 'Consulta de Aeronaves' not in clean(form):
            raise SystemExit('✗ No se pudo abrir el formulario de consulta de aeronaves.')
        return form

    def consulta(self, tipo_busqueda, valor):
        form = self.open_aeronave_form()
        vs = self._viewstate(form)
        url = BASE + FORM_PATH
        data = {
            'params': 'params',
            'params:j_id268': tipo_busqueda,
            'carNumber': valor.upper(),
            'params:j_id279': 'params:j_id279',
            'nombreConsulta': 'Consulta de Aeronaves',
            'numeroConsulta': '26',
            'error': '',
            'javax.faces.ViewState': vs,
        }
        _, h = self._req(url, data, ref=url)
        return parse_result(h), h

    def aeronave_detalle(self, result_html, aeronave):
        vs = self._viewstate(result_html)
        data = {'params': 'params', 'javax.faces.ViewState': vs}
        data.update(aeronave['params'])
        _, h = self._req(BASE + FORM_PATH, data, ref=BASE + FORM_PATH)
        return parse_aeronave_detail(h), h


def clean(s):
    s = re.sub(r'<script\b[^>]*>.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<style\b[^>]*>.*?</style>', ' ', s, flags=re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def parse_jsf_params(pvp):
    parts = pvp.split(',')
    return dict(zip(parts[0::2], parts[1::2]))


def find_aeronave_link(h):
    form_match = re.search(
        r'<form[^>]*id="([^"]*)"[^>]*action="([^"]*)"[^>]*>(.*?)</form>',
        h[h.find('Consultas Gratuitas'):],
        re.S)
    if not form_match:
        return None
    
    fid, action, body = form_match.groups()
    token_re = re.compile(r'<h3>(.*?)</h3>|<a\b([^>]*)>(.*?)</a>', re.S)
    current_section = ''
    
    for m in token_re.finditer(body):
        if m.group(1):
            current_section = clean(m.group(1))
            continue
        attrs, inner = m.group(2), m.group(3)
        text = clean(inner)
        jsf = re.search(r"jsfcljs\(document\.forms\['([^']+)'\],'([^']*)'", attrs)
        if not text or not jsf:
            continue
        if current_section == 'Bienes Muebles' and text == 'Consulta de Aeronaves':
            return {
                'form': jsf.group(1) or fid,
                'action': action,
                'params': parse_jsf_params(jsf.group(2)),
            }
    return None


def parse_aeronaves(h):
    aeronaves = []
    tbody = re.search(r'<tbody[^>]*id="params:j_id381:tb"[^>]*>(.*?)</tbody>', h, re.S)
    if not tbody:
        tbody = re.search(r'<tbody[^>]*>(.*?)</tbody>', h, re.S)
    if not tbody:
        return aeronaves

    for idx, tr in enumerate(re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbody.group(1), re.S), start=1):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.S)
        if len(cells) < 3:
            continue
        matricula = clean(cells[0])
        marca = clean(cells[1])
        modelo = clean(cells[2]) if len(cells) > 2 else ''
        serie = clean(cells[3]) if len(cells) > 3 else ''
        link = re.search(
            r"jsfcljs\(document\.forms\['params'\],'([^']*)'",
            cells[0],
            re.S)
        if not link:
            continue
        aeronaves.append({
            'index': idx,
            'matricula': matricula,
            'marca': marca,
            'modelo': modelo,
            'serie': serie,
            'params': parse_jsf_params(link.group(1)),
        })
    return aeronaves


def parse_result(h):
    text = clean(h)
    tables = []
    for table in re.findall(r'<table\b[^>]*>(.*?)</table>', h, re.S):
        rows = []
        for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table, re.S):
            cells = [clean(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', tr, re.S)]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    notices = []
    for phrase in ('No hay registro', 'NO HAY AERONAVES', 'NO HAY RESULTADOS'):
        if phrase.casefold() in text.casefold():
            notices.append(phrase)
    return {
        'notices': notices,
        'tables': tables,
        'aeronaves': parse_aeronaves(h),
        'text': text,
    }


def first_match(pattern, h):
    m = re.search(pattern, h, re.S | re.I)
    return clean(m.group(1)) if m else ''


def parse_label_pairs(h):
    out = {}
    for m in re.finditer(r'<span class="label">([^<]*):?\s*</span>\s*([^<\n\r]+)', h, re.S | re.I):
        key = clean(m.group(1)).rstrip(':')
        val = clean(m.group(2))
        if key and val and key not in out:
            out[key] = val
    return out


def parse_aeronave_detail(h):
    start = h.find('REPÚBLICA DE COSTA RICA')
    if start < 0:
        start = h.find('MATRÍCULA:')
    end = h.find('<form id="j_id490"', start)
    report_html = h[start:end] if start >= 0 and end > start else h
    text = clean(report_html)
    labels = parse_label_pairs(report_html)

    data = {
        'matricula': labels.get('MATRÍCULA', labels.get('MATRICULA', '')),
        'tipo': labels.get('TIPO', ''),
        'marca': labels.get('MARCA', ''),
        'modelo': labels.get('MODELO', ''),
        'serie': labels.get('SERIE', ''),
        'year': labels.get('AÑO', labels.get('YEAR', '')),
        'motor': labels.get('MOTOR', ''),
        'helice': labels.get('HÉLICE', labels.get('HELICE', '')),
        'propietario': first_match(r'<span class="label">PROPIETARIO:</span>\s*</td>\s*</tr>\s*<tr><td>(.*?)</td>', report_html),
        'anotaciones': first_match(r'<span class="label">ANOTACIONES:\s*([^<]+)</span>', report_html),
        'gravamenes': first_match(r'<span class="label">GRAVAMENES o AFECTACIONES:\s*([^<]+)</span>', report_html),
        'texto': text,
    }
    return data


def print_result(result):
    if result['notices']:
        for notice in result['notices']:
            print(notice)

    printed = False
    for rows in result['tables']:
        if any('Seleccione' in ' '.join(row) for row in rows):
            continue
        if not printed:
            print()
            print('Resultados:')
            printed = True
        for row in rows:
            print(' | '.join(cell or '-' for cell in row))

    if not result['notices'] and not printed:
        print('No se pudo interpretar una tabla de resultados. Respuesta resumida:')
        print(result['text'][:1200])


def safe_name(value):
    value = re.sub(r'[^0-9A-Za-z_.-]+', '_', value.strip())
    return value.strip('_') or 'aeronave'


def default_output_dir(valor):
    return f'AERONAVE_{safe_name(valor).upper()}'


def save_aeronave_files(out_dir, aeronave, detail, html_body):
    os.makedirs(out_dir, exist_ok=True)
    base = safe_name(f'{aeronave["index"]:02d}_{aeronave["matricula"]}')
    json_path = os.path.join(out_dir, base + '.json')
    txt_path = os.path.join(out_dir, base + '.txt')
    html_path = os.path.join(out_dir, base + '.html')

    payload = {'resumen': aeronave, 'detalle': detail}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(render_aeronave_text(aeronave, detail))
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_body)
    return json_path, txt_path, html_path


def render_aeronave_text(aeronave, detail):
    lines = [
        f'Matrícula: {aeronave["matricula"]}',
        f'Marca: {aeronave["marca"]}',
        f'Modelo: {aeronave["modelo"]}',
        f'Serie: {aeronave["serie"] or "-"}',
        '',
    ]
    for key in ('matricula', 'tipo', 'marca', 'modelo', 'serie', 'year',
                'motor', 'helice', 'propietario', 'anotaciones', 'gravamenes'):
        if detail.get(key):
            lines.append(f'{key.replace("_", " ").title()}: {detail[key]}')
    lines.extend(['', 'Texto completo:', detail.get('texto', '')])
    return '\n'.join(lines).rstrip() + '\n'


def load_dotenv(path='.env'):
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v)


def main():
    ap = argparse.ArgumentParser(
        description='Consulta de Aeronaves por Número de Serie o Matrícula en el RNP.')
    ap.add_argument('--serie', help='Número de serie de la aeronave')
    ap.add_argument('--matricula', help='Número de matrícula')
    ap.add_argument('--salida', metavar='DIR',
                    help='Carpeta donde se guardan los HTML, TXT y JSON')
    ap.add_argument('--no-guardar', action='store_true',
                    help='Solo lista resultados; no abre ni guarda el detalle')
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')
    args = ap.parse_args()

    if not args.serie and not args.matricula:
        raise SystemExit('✗ Indique --serie o --matricula.')

    tipo_busqueda = 'serie' if args.serie else 'matricula'
    valor = args.serie or args.matricula

    load_dotenv()
    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')

    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    print(f'• Consultando aeronave por {tipo_busqueda}: {valor}…', file=sys.stderr)
    result, result_html = rnp.consulta(TIPOS_BUSQUEDA[tipo_busqueda], valor)
    print_result(result)

    if not args.no_guardar and result['aeronaves']:
        out_dir = args.salida or default_output_dir(valor)
        print()
        print(f'Guardando detalles de {len(result["aeronaves"])} aeronave(s) en {out_dir}...')
        for aeronave in result['aeronaves']:
            print(f'• Abriendo aeronave {aeronave["matricula"]}...', file=sys.stderr)
            detail, detail_html = rnp.aeronave_detalle(result_html, aeronave)
            json_path, txt_path, html_path = save_aeronave_files(out_dir, aeronave, detail, detail_html)
            print(f'- {aeronave["matricula"]}: {txt_path} | {json_path} | {html_path}')


if __name__ == '__main__':
    main()
