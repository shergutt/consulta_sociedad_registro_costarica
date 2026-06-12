#!/usr/bin/env python3
"""
Lista y abre opciones del indice de documentos del Registro Nacional (RNP).

Uso:
    python3 rnp_indice_documentos.py
    python3 rnp_indice_documentos.py --select "Consulta de Documento"
    RNP_USER=correo@x.com RNP_PASS=MiClave python3 rnp_indice_documentos.py

Credenciales (orden de prioridad): --user/--pass > .env > $RNP_USER/$RNP_PASS > prompt.
"""
import argparse
import getpass
import html
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

    def indice(self):
        url = BASE + INDEX_PATH
        gu, h = self._req(url, ref=BASE + 'login.jspx')
        if 'Consultas Gratuitas' not in h:
            raise SystemExit('✗ No se pudo abrir el índice de documentos. URL: ' + gu)
        return gu, h

    def follow_option(self, page_html, option):
        options = parse_options(page_html)
        needle = normalize(option)
        matches = [o for o in options if needle in normalize(o['text'])]
        if not matches:
            raise SystemExit(f'✗ No encontré una opción que coincida con: {option}')
        if len(matches) > 1:
            print('Coincidencias múltiples:', file=sys.stderr)
            for o in matches:
                print(f'  [{o["num"]}] {o["section"]} - {o["text"]}', file=sys.stderr)
            raise SystemExit('✗ Use un texto más específico.')

        selected = matches[0]
        fid = selected['form']
        action = selected['action']
        vs = self._viewstate(page_html)
        data = {fid: fid, 'javax.faces.ViewState': vs}
        data.update(selected['params'])
        url, h = self._req(self._abs(action), data, ref=BASE + INDEX_PATH)
        return selected, url, h


def clean_text(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def normalize(s):
    return clean_text(s).casefold()


def parse_jsf_params(pvp):
    parts = pvp.split(',')
    return dict(zip(parts[0::2], parts[1::2]))


def parse_options(h):
    form_match = re.search(
        r'<form[^>]*id="([^"]*)"[^>]*action="([^"]*)"[^>]*>(.*?)</form>',
        h[h.find('Consultas Gratuitas'):],
        re.S)
    if not form_match:
        return []

    fid, action, body = form_match.groups()
    current_section = ''
    options = []
    num = 1
    token_re = re.compile(r'<h3>(.*?)</h3>|<a\b([^>]*)>(.*?)</a>', re.S)
    for m in token_re.finditer(body):
        if m.group(1):
            current_section = clean_text(m.group(1))
            continue
        attrs, inner = m.group(2), m.group(3)
        text = clean_text(inner)
        jsf = re.search(r"jsfcljs\(document\.forms\['([^']+)'\],'([^']*)'", attrs)
        if not text or not jsf:
            continue
        options.append({
            'num': num,
            'section': current_section,
            'text': text,
            'form': jsf.group(1),
            'action': action,
            'params': parse_jsf_params(jsf.group(2)),
        })
        num += 1
    return options


def parse_forms_summary(h):
    forms = []
    for m in re.finditer(r'<form[^>]*id="([^"]*)"[^>]*action="([^"]*)"[^>]*>(.*?)</form>', h, re.S):
        fid, action, body = m.groups()
        text = clean_text(body)
        fields = []
        for tag in re.findall(r'<(?:input|select|textarea)\b[^>]*>', body):
            name = re.search(r'name="([^"]*)"', tag)
            typ = re.search(r'type="([^"]*)"', tag)
            if name:
                fields.append((name.group(1), typ.group(1) if typ else 'field'))
        forms.append({'id': fid, 'action': action, 'text': text[:300], 'fields': fields})
    return forms


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
    ap = argparse.ArgumentParser(description='Lista opciones del índice de documentos del RNP.')
    ap.add_argument('--select', help='Texto de la opción que desea abrir, ej. "Consulta de Documento"')
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')
    args = ap.parse_args()

    load_dotenv()
    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')

    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    print('• Abriendo índice de documentos…', file=sys.stderr)
    _, page = rnp.indice()

    if not args.select:
        options = parse_options(page)
        if not options:
            raise SystemExit('✗ No se encontraron opciones en el índice.')
        last_section = None
        for opt in options:
            if opt['section'] != last_section:
                last_section = opt['section']
                print(f'\n{last_section}')
            print(f'  [{opt["num"]:02d}] {opt["text"]}')
        return

    selected, url, h = rnp.follow_option(page, args.select)
    print()
    print(f'Opción : {selected["section"]} - {selected["text"]}')
    print(f'URL    : {url}')
    print()
    print('Formularios encontrados en la página resultante:')
    for form in parse_forms_summary(h):
        print(f'- {form["id"]} -> {form["action"]}')
        if form['text']:
            print(f'  Texto: {form["text"]}')
        if form['fields']:
            rendered = ', '.join(f'{name} ({typ})' for name, typ in form['fields'][:12])
            more = ' ...' if len(form['fields']) > 12 else ''
            print(f'  Campos: {rendered}{more}')


if __name__ == '__main__':
    main()
