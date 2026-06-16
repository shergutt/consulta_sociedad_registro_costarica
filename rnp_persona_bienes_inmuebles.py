#!/usr/bin/env python3
"""
Consulta de Personas por Tipo de Identificacion - Bienes Inmuebles.

Uso:
    python3 rnp_persona_bienes_inmuebles.py 203170516
    python3 rnp_persona_bienes_inmuebles.py 1-1234-5678 --salida resultado_fincas
    python3 rnp_persona_bienes_inmuebles.py 203170516 --no-guardar-fincas
    python3 rnp_persona_bienes_inmuebles.py 3-101-123456 --tipo juridica
    RNP_USER=correo@x.com RNP_PASS=MiClave python3 rnp_persona_bienes_inmuebles.py 112345678

Credenciales (orden de prioridad): --user/--pass > .env > $RNP_USER/$RNP_PASS > prompt.
"""
import argparse
import getpass
import html
from html.parser import HTMLParser
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
FORM_PATH = 'consultaDocumentos/paramConsultaPersonaBI.jspx'

TIPOS = {
    'fisica': '1',
    'cedula': '1',
    'identidad': '1',
    'juridica': '2',
}


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None
        self.section = ''
        self._h3 = None
        self._a = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k: v or '' for k, v in attrs}
        if tag == 'form':
            self.current = {
                'id': attrs_dict.get('id', ''),
                'action': attrs_dict.get('action', ''),
                'inputs': [],
                'links': [],
                'text': [],
            }
            self.section = ''
            return
        if self.current is None:
            return
        if tag == 'input':
            self.current['inputs'].append(attrs_dict)
            for key in ('name', 'value', 'type'):
                if attrs_dict.get(key):
                    self.current['text'].append(attrs_dict[key])
        elif tag == 'h3':
            self._h3 = []
        elif tag == 'a':
            self._a = {'attrs': attrs_dict, 'text': []}

    def handle_data(self, data):
        if self.current is not None and data.strip():
            self.current['text'].append(data)
        if self._h3 is not None:
            self._h3.append(data)
        if self._a is not None:
            self._a['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'h3' and self._h3 is not None:
            self.section = clean(' '.join(self._h3))
            self._h3 = None
        elif tag == 'a' and self._a is not None and self.current is not None:
            self.current['links'].append({
                'section': self.section,
                'text': clean(' '.join(self._a['text'])),
                'attrs': self._a['attrs'],
            })
            self._a = None
        elif tag == 'form' and self.current is not None:
            self.forms.append(self.current)
            self.current = None
            self.section = ''


def parse_forms(h):
    parser = FormParser()
    parser.feed(h or '')
    return parser.forms


def form_contains(form, needle):
    target = (needle or '').casefold()
    if target == 'type="password"':
        return any(i.get('type', '').casefold() == 'password' for i in form['inputs'])
    haystack = ' '.join(form['text']).casefold()
    return target in haystack


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
        for form in parse_forms(h):
            if form_contains(form, needle):
                return form['id'], form['action'], form
        for m in re.finditer(r'<form[^>]*id="([^"]*)"[^>]*action="([^"]*)"[^>]*>(.*?)</form>', h, re.S):
            if needle in m.group(3):
                return m.group(1), m.group(2), m.group(3)
        return None

    @staticmethod
    def _inputs(body):
        if isinstance(body, dict):
            out = {}
            for inp in body.get('inputs', []):
                name = inp.get('name')
                if name:
                    out[name] = {
                        'val': html.unescape(inp.get('value', '')),
                        'type': inp.get('type', ''),
                    }
            return out
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
            si = next((n for n, mt in mf.items()
                       if mt['type'] == 'submit' and 'continuar' in mt['val'].lower()), None)
            if not mfid or not mact or not si:
                raise SystemExit('✗ No se pudo cerrar la sesión activa del RNP.')
            d = {mfid: mfid}
            for n, meta in mf.items():
                if meta['type'] == 'hidden' and n not in d:
                    d[n] = meta['val']
            d[si] = mf[si]['val']
            d.setdefault('javax.faces.ViewState', self._viewstate(h))
            _, mh = self._req(self._abs(mact), d, ref=BASE + 'login.jspx')
            if 'modalSesionActiva' in mh:
                raise SystemExit('✗ El RNP mantiene otra sesión activa y no aceptó cerrarla automáticamente.')

    def open_persona_bi_form(self):
        index_url = BASE + INDEX_PATH
        _, h = self._req(index_url, ref=BASE + 'login.jspx')
        vs = self._viewstate(h)
        link = find_bienes_inmuebles_persona_link(h)
        if not vs or not link:
            raise SystemExit('✗ No se encontró la opción de Bienes Inmuebles por identificación.')
        data = {
            link['form']: link['form'],
            'javax.faces.ViewState': vs,
        }
        data.update(link['params'])
        _, form = self._req(self._abs(link['action']), data, ref=index_url)
        if 'Consulta de Personas por Tipo de Identificación - Bienes Inmuebles' not in clean(form):
            raise SystemExit('✗ No se pudo abrir el formulario de consulta.')
        return form

    def consulta(self, tipo, partes):
        form = self.open_persona_bi_form()
        vs = self._viewstate(form)
        url = BASE + FORM_PATH
        data = {
            'params': 'params',
            'params:j_id269': tipo,
            'javax.faces.ViewState': vs,
            'AJAXREQUEST': 'params',
            'params:j_id341': 'params:j_id341',
            'operacion': 'search',
            'page': '1',
        }
        if tipo == '1':
            data.update({
                'params:cedula1': partes[0],
                'params:cedula2': partes[1],
                'params:cedula3': partes[2],
            })
        elif tipo == '2':
            data.update({
                'params:cedulaJuridica1': partes[0],
                'params:cedulaJuridica2': partes[1],
                'params:cedulaJuridica3': partes[2],
            })
        else:
            raise SystemExit('✗ Tipo de identificación no implementado en este script.')
        _, h = self._req(url, data, ref=url, ajax=True)
        return parse_result(h), h

    def finca_detalle(self, result_html, finca):
        vs = self._viewstate(result_html)
        data = {'params': 'params', 'javax.faces.ViewState': vs}
        data.update(finca['params'])
        _, h = self._req(BASE + FORM_PATH, data, ref=BASE + FORM_PATH)
        return parse_finca_detail(h), h


def clean(s):
    s = re.sub(r'<script\b[^>]*>.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<style\b[^>]*>.*?</style>', ' ', s, flags=re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def parse_jsf_params(pvp):
    parts = pvp.split(',')
    return dict(zip(parts[0::2], parts[1::2]))


def find_bienes_inmuebles_persona_link(h):
    for form in parse_forms(h):
        fid = form['id']
        action = form['action']
        if 'Consultas Gratuitas' not in clean(' '.join(form['text'])):
            continue
        for link in form['links']:
            if link['section'] != 'Bienes Inmuebles' or link['text'] != 'Consulta de Personas por Identificación':
                continue
            attrs = ' '.join(str(v) for v in link['attrs'].values())
            jsf = re.search(r"jsfcljs\(document\.forms\['([^']+)'\],'([^']*)'", attrs)
            if not jsf:
                continue
            return {
                'form': jsf.group(1) or fid,
                'action': action,
                'params': parse_jsf_params(jsf.group(2)),
            }
    return None


def parse_id(raw, tipo):
    digits = re.sub(r'\D', '', raw)
    if tipo == '1':
        if len(digits) != 9:
            raise SystemExit('✗ La cédula física debe tener 9 dígitos, ej. 1-1234-5678.')
        return digits[0], digits[1:5], digits[5:]
    if tipo == '2':
        if len(digits) not in (10, 11):
            raise SystemExit('✗ La cédula jurídica debe tener 10 u 11 dígitos, ej. 3-101-123456.')
        return digits[0], digits[1:4], digits[4:]
    raise SystemExit('✗ Tipo de identificación no soportado.')


def parse_fincas(h):
    fincas = []
    tbody = re.search(r'<tbody[^>]*id="params:j_id381:tb"[^>]*>(.*?)</tbody>', h, re.S)
    if not tbody:
        return fincas

    for idx, tr in enumerate(re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbody.group(1), re.S), start=1):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.S)
        if len(cells) < 5:
            continue
        provincia = clean(cells[0])
        horizontal = clean(cells[1])
        numero = clean(cells[2])
        duplicado = clean(cells[3])
        derecho = clean(cells[4])
        link = re.search(
            r"jsfcljs\(document\.forms\['params'\],'([^']*numeroConsulta,1[^']*)'",
            cells[2],
            re.S)
        if not link:
            continue
        fincas.append({
            'index': idx,
            'provincia': provincia,
            'horizontal': horizontal,
            'numero': numero,
            'duplicado': duplicado,
            'derecho': derecho,
            'params': parse_jsf_params(link.group(1)),
        })
    return fincas


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
    for phrase in ('No hay registro de esa persona.', 'NO HAY FINCAS', 'NO HAY GRAVAMENES'):
        if phrase.casefold() in text.casefold():
            notices.append(phrase)
    return {
        'nombre': parse_person_name(h),
        'notices': notices,
        'tables': tables,
        'fincas': parse_fincas(h),
        'text': text,
    }


def parse_person_name(h):
    ignored = {'FINCAS', 'NO HAY FINCAS', 'NO HAY GRAVAMENES', 'NO HAY GRAVÁMENES'}
    for value in re.findall(r'<span[^>]*class="titulo"[^>]*>(.*?)</span>', h, re.S | re.I):
        title = clean(value)
        if title and title.upper() not in ignored:
            return title
    return ''


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


def parse_rich_table_by_title(h, title):
    title_pos = clean(h).casefold().find(title.casefold())
    if title_pos < 0:
        return []

    tables = []
    for table in re.findall(r'<table\b[^>]*class="[^"]*rich-table[^"]*"[^>]*>(.*?)</table>', h, re.S):
        rows = []
        for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', table, re.S):
            cells = [clean(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', tr, re.S)]
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def parse_finca_detail(h):
    start = h.find('REPÚBLICA DE COSTA RICA')
    if start < 0:
        start = h.find('MATRÍCULA:')
    end = h.find('<form id="j_id490"', start)
    report_html = h[start:end] if start >= 0 and end > start else h
    text = clean(report_html)
    labels = parse_label_pairs(report_html)
    matricula = first_match(r'MATR[IÍ]CULA:\s*([^<]+)<', h)
    propietario = first_match(r'<span class="label">PROPIETARIO:</span>\s*</td>\s*</tr>\s*<tr><td>(.*?)</td>', report_html)

    data = {
        'matricula': matricula,
        'provincia': labels.get('PROVINCIA', ''),
        'finca': labels.get('FINCA', ''),
        'duplicado': labels.get('DUPLICADO', ''),
        'horizontal': labels.get('HORIZONTAL', ''),
        'derecho': labels.get('DERECHO', ''),
        'naturaleza': labels.get('NATURALEZA', ''),
        'ubicacion': first_match(r'<span class="label">(SITUADA EN.*?)</span>', report_html),
        'zona_catastrada': first_match(r'<span[^>]*color:\s*#298A08[^>]*>(.*?)</span>', report_html),
        'medida': labels.get('MIDE', ''),
        'plano': labels.get('PLANO', ''),
        'antecedentes': first_match(r'(<br />LOS ANTECEDENTES.*?)</td>', report_html),
        'identificador_predial': labels.get('IDENTIFICADOR PREDIAL', ''),
        'valor_fiscal': labels.get('VALOR FISCAL', ''),
        'propietario': propietario,
        'anotaciones': first_match(r'<span class="label">ANOTACIONES SOBRE LA FINCA:\s*([^<]+)</span>', report_html),
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
        # Skip the search form table; result tables normally have several data rows.
        if any('Seleccione el Tipo de Búsqueda' in ' '.join(row) for row in rows):
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
    return value.strip('_') or 'finca'


def default_output_dir(nombre, identificacion):
    digits = re.sub(r'\D', '', identificacion)
    first_name = safe_name((nombre or 'RNP').split()[0]).upper()
    return f'{first_name}_{digits}'


def save_finca_files(out_dir, finca, detail, html_body):
    os.makedirs(out_dir, exist_ok=True)
    base = safe_name(f'{finca["index"]:02d}_{finca["provincia"]}_{finca["numero"]}_{finca["derecho"]}')
    json_path = os.path.join(out_dir, base + '.json')
    txt_path = os.path.join(out_dir, base + '.txt')
    html_path = os.path.join(out_dir, base + '.html')

    payload = {'resumen': finca, 'detalle': detail}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(render_finca_text(finca, detail))
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_body)
    return json_path, txt_path, html_path


def render_finca_text(finca, detail):
    lines = [
        f'Finca: {finca["provincia"]} {finca["numero"]}',
        f'Horizontal: {finca["horizontal"] or "-"}',
        f'Duplicado: {finca["duplicado"] or "-"}',
        f'Derecho: {finca["derecho"] or "-"}',
        '',
    ]
    for key in (
        'matricula',
        'provincia',
        'finca',
        'naturaleza',
        'ubicacion',
        'zona_catastrada',
        'medida',
        'plano',
        'antecedentes',
        'identificador_predial',
        'valor_fiscal',
        'propietario',
        'anotaciones',
        'gravamenes',
    ):
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
        description='Consulta Personas por Tipo de Identificación - Bienes Inmuebles en el RNP.')
    ap.add_argument('identificacion', nargs='?', help='Cédula con o sin guiones')
    ap.add_argument('--tipo', default='fisica', choices=sorted(TIPOS),
                    help='Tipo de identificación: fisica/cedula/identidad o juridica')
    ap.add_argument('--salida', metavar='DIR',
                    help='Carpeta donde se guardan los HTML, TXT y JSON de cada finca')
    ap.add_argument('--guardar-fincas', metavar='DIR',
                    help='Alias antiguo de --salida')
    ap.add_argument('--no-guardar-fincas', action='store_true',
                    help='Solo lista resultados; no abre ni guarda el detalle de cada finca')
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')
    args = ap.parse_args()

    load_dotenv()
    tipo = TIPOS[args.tipo]
    identificacion = args.identificacion or input('Identificación: ').strip()
    partes = parse_id(identificacion, tipo)

    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')

    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    print('• Consultando Personas por Identificación - Bienes Inmuebles…', file=sys.stderr)
    result, result_html = rnp.consulta(tipo, partes)
    print_result(result)

    out_dir = args.salida or args.guardar_fincas or default_output_dir(result.get('nombre'), identificacion)
    if not args.no_guardar_fincas and result['fincas']:
        print()
        print(f'Guardando detalles de {len(result["fincas"])} finca(s) en {out_dir}...')
        for finca in result['fincas']:
            print(f'• Abriendo finca {finca["provincia"]} {finca["numero"]}...', file=sys.stderr)
            detail, detail_html = rnp.finca_detalle(result_html, finca)
            json_path, txt_path, html_path = save_finca_files(out_dir, finca, detail, detail_html)
            print(f'- {finca["numero"]}: {txt_path} | {json_path} | {html_path}')


if __name__ == '__main__':
    main()
