#!/usr/bin/env python3
"""
Consulta de Buques por Matricula, Casco, Motor, Nombre o Serie en el Registro Nacional.

Uso:
    python3 rnp_buques.py --matricula 12345
    python3 rnp_buques.py --casco CASCO123
    python3 rnp_buques.py --motor MOTOR456
    python3 rnp_buques.py --nombre "TITANIC"
    python3 rnp_buques.py --serie SERIE789
    python3 rnp_buques.py --matricula 12345 --clase GPC
    python3 rnp_buques.py --matricula 12345 --salida buques
    python3 rnp_buques.py --matricula 12345 --no-guardar
    RNP_USER=correo@x.com RNP_PASS=MiClave python3 rnp_buques.py --matricula 12345

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
FORM_PATH = 'consultaDocumentos/bienesMuebles/paramConsultaBuque.jspx'

TIPOS_BUSQUEDA = {
    'matricula': 'MAT',
    'casco': 'CHA',
    'motor': 'MOT',
    'nombre': 'NOM',
    'serie': 'SER',
}

CLASES = {
    'gpc': 'GPC',
    'l': 'L',
    'ma': 'MA',
    'p': 'P',
    'pg': 'PG',
    'pq': 'PQ',
    'tme': 'TME',
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

    def open_buque_form(self):
        index_url = BASE + INDEX_PATH
        _, h = self._req(index_url, ref=BASE + 'login.jspx')
        vs = self._viewstate(h)
        link = find_buque_link(h)
        if not vs or not link:
            raise SystemExit('✗ No se encontró la opción de Consulta de Buques.')
        data = {
            link['form']: link['form'],
            'javax.faces.ViewState': vs,
        }
        data.update(link['params'])
        _, form = self._req(self._abs(link['action']), data, ref=index_url)
        if 'Consulta de Buques' not in clean(form):
            raise SystemExit('✗ No se pudo abrir el formulario de consulta de buques.')
        return form

    def consulta(self, tipo_busqueda, valor, clase=None):
        form = self.open_buque_form()
        vs = self._viewstate(form)
        url = BASE + FORM_PATH
        data = {
            'params': 'params',
            'params:j_id266': tipo_busqueda,
            'params:j_id314': valor.upper(),
            'params:j_id318': 'params:j_id318',
            'nombreConsulta': 'Busqueda Matricula Buque',
            'numeroConsulta': '35',
            'javax.faces.ViewState': vs,
        }
        if clase:
            data['params:j_id305'] = clase
        _, h = self._req(url, data, ref=url)
        return parse_result(h), h

    def buque_detalle(self, result_html, buque):
        vs = self._viewstate(result_html)
        data = {'params': 'params', 'javax.faces.ViewState': vs}
        data.update(buque['params'])
        _, h = self._req(BASE + FORM_PATH, data, ref=BASE + FORM_PATH)
        return parse_buque_detail(h), h


def clean(s):
    s = re.sub(r'<script\b[^>]*>.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<style\b[^>]*>.*?</style>', ' ', s, flags=re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def parse_jsf_params(pvp):
    parts = pvp.split(',')
    return dict(zip(parts[0::2], parts[1::2]))


def find_buque_link(h):
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
        if current_section == 'Bienes Muebles' and text == 'Consulta de Buques':
            return {
                'form': jsf.group(1) or fid,
                'action': action,
                'params': parse_jsf_params(jsf.group(2)),
            }
    return None


def parse_buques(h):
    buques = []
    tbody = re.search(r'<tbody[^>]*id="params:j_id381:tb"[^>]*>(.*?)</tbody>', h, re.S)
    if not tbody:
        tbody = re.search(r'<tbody[^>]*>(.*?)</tbody>', h, re.S)
    if not tbody:
        return buques

    for idx, tr in enumerate(re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbody.group(1), re.S), start=1):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.S)
        if len(cells) < 3:
            continue
        matricula = clean(cells[0])
        nombre = clean(cells[1])
        tipo = clean(cells[2]) if len(cells) > 2 else ''
        clase = clean(cells[3]) if len(cells) > 3 else ''
        link = re.search(
            r"jsfcljs\(document\.forms\['params'\],'([^']*)'",
            cells[0],
            re.S)
        if not link:
            continue
        buques.append({
            'index': idx,
            'matricula': matricula,
            'nombre': nombre,
            'tipo': tipo,
            'clase': clase,
            'params': parse_jsf_params(link.group(1)),
        })
    return buques


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
    for phrase in ('No hay registro', 'NO HAY BUQUES', 'NO HAY RESULTADOS'):
        if phrase.casefold() in text.casefold():
            notices.append(phrase)
    return {
        'notices': notices,
        'tables': tables,
        'buques': parse_buques(h),
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


def parse_buque_detail(h):
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
        'nombre': labels.get('NOMBRE', ''),
        'clase': labels.get('CLASE', ''),
        'eslora': labels.get('ESLORA', ''),
        'manga': labels.get('MANGA', ''),
        'puntal': labels.get('PUNTAL', ''),
        'tonelaje_bruto': labels.get('TONELAJE BRUTO', ''),
        'tonelaje_neto': labels.get('TONELAJE NETO', ''),
        'motor': labels.get('MOTOR', ''),
        'casco': labels.get('CASCO', ''),
        'serie': labels.get('SERIE', ''),
        'year': labels.get('AÑO', labels.get('YEAR', '')),
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
    return value.strip('_') or 'buque'


def default_output_dir(valor):
    return f'BUQUE_{safe_name(valor).upper()}'


def save_buque_files(out_dir, buque, detail, html_body):
    os.makedirs(out_dir, exist_ok=True)
    base = safe_name(f'{buque["index"]:02d}_{buque["matricula"]}_{buque["nombre"]}')
    json_path = os.path.join(out_dir, base + '.json')
    txt_path = os.path.join(out_dir, base + '.txt')
    html_path = os.path.join(out_dir, base + '.html')

    payload = {'resumen': buque, 'detalle': detail}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(render_buque_text(buque, detail))
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_body)
    return json_path, txt_path, html_path


def render_buque_text(buque, detail):
    lines = [
        f'Matrícula: {buque["matricula"]}',
        f'Nombre: {buque["nombre"]}',
        f'Tipo: {buque["tipo"]}',
        f'Clase: {buque["clase"] or "-"}',
        '',
    ]
    for key in ('matricula', 'tipo', 'nombre', 'clase', 'eslora', 'manga', 'puntal',
                'tonelaje_bruto', 'tonelaje_neto', 'motor', 'casco', 'serie', 'year',
                'propietario', 'anotaciones', 'gravamenes'):
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
        description='Consulta de Buques por Matrícula, Casco, Motor, Nombre o Serie en el RNP.')
    ap.add_argument('--matricula', help='Número de matrícula')
    ap.add_argument('--casco', help='Número de casco')
    ap.add_argument('--motor', help='Número de motor')
    ap.add_argument('--nombre', help='Nombre del buque')
    ap.add_argument('--serie', help='Número de serie')
    ap.add_argument('--clase', choices=sorted(CLASES), help='Clase del buque (GPC, L, MA, P, PG, PQ, TME)')
    ap.add_argument('--salida', metavar='DIR',
                    help='Carpeta donde se guardan los HTML, TXT y JSON')
    ap.add_argument('--no-guardar', action='store_true',
                    help='Solo lista resultados; no abre ni guarda el detalle')
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')
    args = ap.parse_args()

    tipo_busqueda = None
    valor = None
    
    if args.matricula:
        tipo_busqueda = 'matricula'
        valor = args.matricula
    elif args.casco:
        tipo_busqueda = 'casco'
        valor = args.casco
    elif args.motor:
        tipo_busqueda = 'motor'
        valor = args.motor
    elif args.nombre:
        tipo_busqueda = 'nombre'
        valor = args.nombre
    elif args.serie:
        tipo_busqueda = 'serie'
        valor = args.serie
    
    if not valor:
        raise SystemExit('✗ Indique --matricula, --casco, --motor, --nombre o --serie.')

    clase = CLASES.get(args.clase.lower()) if args.clase else None

    load_dotenv()
    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')

    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    print(f'• Consultando buque por {tipo_busqueda}: {valor}…', file=sys.stderr)
    result, result_html = rnp.consulta(TIPOS_BUSQUEDA[tipo_busqueda], valor, clase)
    print_result(result)

    if not args.no_guardar and result['buques']:
        out_dir = args.salida or default_output_dir(valor)
        print()
        print(f'Guardando detalles de {len(result["buques"])} buque(s) en {out_dir}...')
        for buque in result['buques']:
            print(f'• Abriendo buque {buque["matricula"]}...', file=sys.stderr)
            detail, detail_html = rnp.buque_detalle(result_html, buque)
            json_path, txt_path, html_path = save_buque_files(out_dir, buque, detail, detail_html)
            print(f'- {buque["matricula"]}: {txt_path} | {json_path} | {html_path}')


if __name__ == '__main__':
    main()
