#!/usr/bin/env python3
"""
Consulta de Personas por Tipo de Identificacion - Bienes Muebles.

Uso:
    python3 rnp_persona_bienes_muebles.py 203170516
    python3 rnp_persona_bienes_muebles.py 1-1234-5678 --salida resultado_muebles
    python3 rnp_persona_bienes_muebles.py 203170516 --no-guardar
    python3 rnp_persona_bienes_muebles.py 3-101-123456 --tipo juridica
    RNP_USER=correo@x.com RNP_PASS=MiClave python3 rnp_persona_bienes_muebles.py 112345678

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
FORM_PATH = 'consultaDocumentos/bienesMuebles/paramConsultaPersona.jspx'

TIPOS_ID = {
    'fisica': '000001',
    'cedula': '000001',
    'identidad': '000001',
    'residente': '000002',
    'juridica': '000003',
    'menor': '000004',
    'pensionado': '000005',
    'pasaporte': '000006',
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

    def open_persona_bm_form(self):
        index_url = BASE + INDEX_PATH
        _, h = self._req(index_url, ref=BASE + 'login.jspx')
        vs = self._viewstate(h)
        link = find_bm_persona_link(h)
        if not vs or not link:
            raise SystemExit('✗ No se encontró la opción de Bienes Muebles por identificación.')
        data = {
            link['form']: link['form'],
            'javax.faces.ViewState': vs,
        }
        data.update(link['params'])
        _, form = self._req(self._abs(link['action']), data, ref=index_url)
        if 'Consulta de Persona por Tipo de Identificación - Bienes Muebles' not in clean(form):
            raise SystemExit('✗ No se pudo abrir el formulario de consulta.')
        return form

    def consulta(self, tipo_id, partes):
        form = self.open_persona_bm_form()
        vs = self._viewstate(form)
        url = BASE + FORM_PATH
        data = {
            'params': 'params',
            'params:j_id268': tipo_id,
            'cedulaFisicaPrimeraParte': partes[0],
            'cedulaFisicaSegundaParte': partes[1],
            'cedulaFisicaTerceraParte': partes[2],
            'params:j_id448': 'params:j_id448',
            'nombreConsulta': 'Indice de Personas',
            'numeroConsulta': '47',
            'javax.faces.ViewState': vs,
            'AJAXREQUEST': 'params',
            'operacion': 'search',
            'page': '1',
        }
        _, h = self._req(url, data, ref=url, ajax=True)
        return parse_result(h), h

    def bien_detalle(self, result_html, bien):
        vs = self._viewstate(result_html)
        data = {'params': 'params', 'javax.faces.ViewState': vs}
        data.update(bien['params'])
        url1, h1 = self._req(BASE + FORM_PATH, data, ref=BASE + FORM_PATH)
        link2 = re.search(r"jsfcljs\(document\.forms\['(j_id\d+)'\],'([^']*bienLink[^']*)'", h1)
        if not link2:
            return parse_bien_detail(h1), h1
        form_id2 = link2.group(1)
        params2 = parse_jsf_params(link2.group(2))
        act2 = re.search(rf'<form[^>]*id="{form_id2}"[^>]*action="([^"]*)"', h1)
        url2 = self._abs(act2.group(1)) if act2 else url1
        vs2 = self._viewstate(h1)
        data2 = {form_id2: form_id2, 'javax.faces.ViewState': vs2}
        data2.update(params2)
        url3, h2 = self._req(url2, data2, ref=url1)
        return parse_bien_detail(h2), h2


def clean(s):
    s = re.sub(r'<script\b[^>]*>.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<style\b[^>]*>.*?</style>', ' ', s, flags=re.S | re.I)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def parse_jsf_params(pvp):
    parts = pvp.split(',')
    return dict(zip(parts[0::2], parts[1::2]))


def find_bm_persona_link(h):
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
        if current_section == 'Bienes Muebles' and text == 'Consulta de Personas por Identificación':
            return {
                'form': jsf.group(1) or fid,
                'action': action,
                'params': parse_jsf_params(jsf.group(2)),
            }
    return None


def parse_id(raw, tipo):
    digits = re.sub(r'\D', '', raw)
    if tipo in ('000001', '000002', '000004', '000005', '000006'):
        if len(digits) != 9:
            raise SystemExit('✗ La cédula física debe tener 9 dígitos, ej. 1-1234-5678.')
        return digits[0], digits[1:5], digits[5:]
    if tipo == '000003':
        if len(digits) not in (10, 11):
            raise SystemExit('✗ La cédula jurídica debe tener 10 u 11 dígitos, ej. 3-101-123456.')
        return digits[0], digits[1:4], digits[4:]
    if len(digits) == 9:
        return digits[0], digits[1:5], digits[5:]
    if len(digits) in (10, 11):
        return digits[0], digits[1:4], digits[4:]
    raise SystemExit('✗ Formato de identificación no reconocido.')


def parse_bienes(h):
    bienes = []
    # Buscar cualquier tbody que termine en :tb (el ID puede variar)
    tbody = re.search(r'<tbody[^>]*id="[^"]*:tb"[^>]*>(.*?)</tbody>', h, re.S)
    if not tbody:
        return bienes

    for idx, tr in enumerate(re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbody.group(1), re.S), start=1):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.S)
        if len(cells) < 4:
            continue
        # Columnas: Índice, Detalle, Detalle (con enlace), Identificación, Nombre
        indice = clean(cells[0])
        identificacion = clean(cells[3]) if len(cells) > 3 else ''
        nombre = clean(cells[4]) if len(cells) > 4 else ''
        
        # Buscar el enlace "Bien Mueble" que contiene los parámetros
        link = re.search(r"jsfcljs\(document\.forms\['params'\],'([^']*)'", cells[2] if len(cells) > 2 else '')
        if not link:
            continue
        
        bienes.append({
            'index': idx,
            'identificacion': identificacion,
            'nombre': nombre,
            'params': parse_jsf_params(link.group(1)),
        })
    return bienes


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
    for phrase in ('No hay registro', 'NO HAY BIENES', 'NO HAY REGISTROS'):
        if phrase.casefold() in text.casefold():
            notices.append(phrase)
    
    # Extraer nombre de la persona de la tabla de resultados
    nombre = ''
    nombre_match = re.search(r'<div[^>]*id="[^"]*:two"[^>]*>(.*?)</div>', h, re.S)
    if nombre_match:
        nombre = clean(nombre_match.group(1))
    
    return {
        'nombre': nombre,
        'notices': notices,
        'tables': tables,
        'bienes': parse_bienes(h),
        'text': text,
    }


def parse_person_name(h):
    ignored = {'BIENES', 'NO HAY BIENES', 'NO HAY REGISTROS'}
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


def parse_bien_detail(h):
    text = clean(h)
    data = {
        'placa': first_match(r'Placa:\s*([A-Z0-9]+)', text),
        'tomo': first_match(r'Tomo:\s*(\d+)', text),
        'asiento': first_match(r'Asiento:\s*(\d+)', text),
        'fecha': first_match(r'Fecha:\s*(\d{2}-\w{3}-\d{4})', text),
        'marca': first_match(r'Marca:\s*([A-Z0-9\s]+?)(?=\s+Estilo:)', text),
        'estilo': first_match(r'Estilo:\s*([A-Z0-9\s]+?)(?=\s+Categor)', text),
        'categoria': first_match(r'Categor[aí]a:\s*([A-Z\s]+?)(?=\s+Capacidad)', text),
        'capacidad': first_match(r'Capacidad:\s*(\d+\s*personas?)', text),
        'chasis': first_match(r'#\s*de\s*Chasis:\s*([A-Z0-9]+)', text),
        'serie': first_match(r'#\s*de\s*Serie:\s*([A-Z0-9]+)', text),
        'vin': first_match(r'#\s*de\s*VIN:\s*([A-Z0-9]+)', text),
        'motor': first_match(r'N\.Motor:\s*([A-Z0-9]+)', text),
        'cilindrada': first_match(r'Cilindrada:\s*(\d+\s*C\.C)', text),
        'cilindros': first_match(r'Cilindros:\s*(\d+)', text),
        'potencia': first_match(r'Potencia:\s*(\d+\s*KW)', text),
        'combustible': first_match(r'Combustible:\s*([A-Z\s]+?)(?=\s+Fabricante)', text),
        'color': first_match(r'Color:\s*([A-Z\s]+?)(?=\s+Numero)', text),
        'anio': first_match(r'A[nñ]o\s*Fabricaci[oó]n:\s*(\d{4})', text),
        'estado': first_match(r'Estado\s*Actual:\s*([A-Z\s]+?)(?=\s+Longitud)', text),
        'uso': first_match(r'Uso:\s*([A-Z\s]+?)(?=\s+Peso\s*Remolque)', text),
        'propietario': first_match(r'CEDULA\s*DE\s*IDENTIDAD\s*(\d+)\s*([A-Z\s]+?)(?=\s*No\s*Posee|\s*Todos\s*los)', text),
        'cedula_propietario': first_match(r'CEDULA\s*DE\s*IDENTIDAD\s*(\d+)', text),
        'texto': text,
    }
    return data


def print_result(result):
    if result['notices']:
        for notice in result['notices']:
            print(notice)

    if result['nombre']:
        print(f'\nNombre: {result["nombre"]}')

    if result['bienes']:
        print(f'\nBienes muebles encontrados: {len(result["bienes"])}')
        print()
        for bien in result['bienes']:
            print(f'  {bien["index"]}. {bien["identificacion"]} - {bien["nombre"]}')
    elif not result['notices']:
        print('\nNo se encontraron bienes muebles para esta persona.')


def safe_name(value):
    value = re.sub(r'[^0-9A-Za-z_.-]+', '_', value.strip())
    return value.strip('_') or 'bien'


def first_value(*values, default=''):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def bien_summary_fields(bien, detail):
    tipo = first_value(
        bien.get('tipo'),
        detail.get('tipo'),
        detail.get('categoria'),
        default='bien_mueble',
    )
    numero = first_value(
        bien.get('numero'),
        detail.get('placa'),
        detail.get('matricula'),
        detail.get('serie'),
        detail.get('vin'),
        detail.get('motor'),
        bien.get('identificacion'),
        bien.get('index'),
        default='sin_numero',
    )
    derecho = first_value(bien.get('derecho'), default='')
    estado = first_value(bien.get('estado'), detail.get('estado'), default='')
    return tipo, numero, derecho, estado


def default_output_dir(nombre, identificacion):
    digits = re.sub(r'\D', '', identificacion)
    first_name = safe_name((nombre or 'RNP').split()[0]).upper()
    return f'{first_name}_{digits}_muebles'


def save_bien_files(out_dir, bien, detail, html_body):
    os.makedirs(out_dir, exist_ok=True)
    tipo, numero, derecho, _ = bien_summary_fields(bien, detail)
    base = safe_name(f'{int(bien.get("index") or 0):02d}_{tipo}_{numero}_{derecho or "000"}')
    json_path = os.path.join(out_dir, base + '.json')
    txt_path = os.path.join(out_dir, base + '.txt')
    html_path = os.path.join(out_dir, base + '.html')

    enriched = {
        **bien,
        'tipo': tipo,
        'numero': numero,
        'derecho': derecho,
        'estado': bien.get('estado') or detail.get('estado') or '',
    }
    payload = {'resumen': enriched, 'detalle': detail}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(render_bien_text(enriched, detail))
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_body)
    return json_path, txt_path, html_path


def render_bien_text(bien, detail):
    tipo, numero, derecho, estado = bien_summary_fields(bien, detail)
    lines = [
        f'Tipo: {tipo}',
        f'Número: {numero}',
        f'Derecho: {derecho or "-"}',
        f'Estado: {estado or "-"}',
        '',
    ]
    for key in ('tipo', 'numero', 'descripcion', 'marca', 'modelo', 'year', 'anio', 'color',
                'serie', 'vin', 'motor', 'chasis', 'placa', 'propietario',
                'cedula_propietario', 'anotaciones', 'gravamenes'):
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
        description='Consulta Personas por Tipo de Identificación - Bienes Muebles en el RNP.')
    ap.add_argument('identificacion', nargs='?', help='Cédula con o sin guiones')
    ap.add_argument('--tipo', default='fisica', choices=sorted(TIPOS_ID),
                    help='Tipo de identificación')
    ap.add_argument('--salida', metavar='DIR',
                    help='Carpeta donde se guardan los HTML, TXT y JSON de cada bien')
    ap.add_argument('--no-guardar', action='store_true',
                    help='Solo lista resultados; no abre ni guarda el detalle')
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')
    args = ap.parse_args()

    load_dotenv()
    tipo = TIPOS_ID[args.tipo]
    identificacion = args.identificacion or input('Identificación: ').strip()
    partes = parse_id(identificacion, tipo)

    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')

    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    print('• Consultando Bienes Muebles por Identificación…', file=sys.stderr)
    result, result_html = rnp.consulta(tipo, partes)
    print_result(result)

    out_dir = args.salida or default_output_dir(result.get('nombre'), identificacion)
    if not args.no_guardar and result['bienes']:
        print()
        print(f'Guardando detalles de {len(result["bienes"])} bien(es) en {out_dir}...')
        for bien in result['bienes']:
            print(f'• Abriendo bien {bien["index"]} {bien["identificacion"]}...', file=sys.stderr)
            detail, detail_html = rnp.bien_detalle(result_html, bien)
            json_path, txt_path, html_path = save_bien_files(out_dir, bien, detail, detail_html)
            tipo, numero, _, _ = bien_summary_fields(bien, detail)
            print(f'- {tipo} {numero}: {txt_path} | {json_path} | {html_path}')


if __name__ == '__main__':
    main()
