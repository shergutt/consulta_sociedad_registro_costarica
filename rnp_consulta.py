#!/usr/bin/env python3
"""
Consulta el nombre / razón social de una persona jurídica de Costa Rica
en el Registro Nacional (rnpdigital.com), a partir de su cédula jurídica.

La consulta gratuita del RNP requiere una cuenta registrada e iniciar sesión.
El sitio permite UNA sola sesión activa por usuario: si ya hay una abierta
(p. ej. en tu navegador), este script la cierra y crea una nueva.

Uso:
    python3 rnp_consulta.py 3109766273
    python3 rnp_consulta.py 3-109-766273 --user correo@x.com --pass MiClave
    RNP_USER=correo@x.com RNP_PASS=MiClave python3 rnp_consulta.py 3109766273

Credenciales (orden de prioridad): --user/--pass  >  $RNP_USER/$RNP_PASS  >  prompt interactivo.
"""
import argparse, getpass, html, os, re, ssl, sys, urllib.parse, urllib.request, http.cookiejar

UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36')
BASE = 'https://www.rnpdigital.com/shopping/'
ROOT = 'https://www.rnpdigital.com'
FORM_PATH = 'consultaDocumentos/paramConsultaJuridicaCedula.jspx'


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

    # ---- helpers ----
    @staticmethod
    def _viewstate(h):
        m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]*)"', h)
        return m.group(1) if m else None

    @staticmethod
    def _form(h, needle):
        """Return (id, action, body) of the first <form> whose body contains `needle`."""
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

    # ---- flow ----
    def login(self, email, password):
        _, h = self._req(BASE + 'login.jspx')
        fid, act, body = self._form(h, 'type="password"')
        fields = self._inputs(body)
        vs = self._viewstate(h)
        action = self._abs(act)

        common = {fid: fid, fid + ':correo': email, fid + ':pass': password,
                  'javax.faces.ViewState': vs}
        for n, meta in fields.items():            # carry hidden tokens (e.g. j_id18)
            if meta['type'] == 'hidden' and n not in common:
                common[n] = meta['val']

        # A4J ajax submit of the "Ingresar" button (j_id26)
        btn = next((n for n in fields if re.fullmatch(re.escape(fid) + r':j_id\d+', n)
                    and fields[n]['type'] == 'button'), fid + ':j_id26')
        d = dict(common); d['AJAXREQUEST'] = fid; d[btn] = btn
        _, lh = self._req(action, d, ref=BASE + 'login.jspx', ajax=True)

        if 'incorrect' in lh.lower() or 'no es correc' in lh.lower():
            raise SystemExit('✗ Credenciales incorrectas según el RNP.')

        # "Sesión activa" -> confirm to kill the other session and continue
        if 'modalSesionActiva' in lh:
            mfid, mact, mbody = self._form(h, 'continuar')
            mf = self._inputs(mbody)
            si = next(n for n, mt in mf.items()
                      if mt['type'] == 'submit' and 'continuar' in mt['val'].lower())
            d = {mfid: mfid, si: mf[si]['val'], 'javax.faces.ViewState': self._viewstate(h)}
            self._req(self._abs(mact), d, ref=BASE + 'login.jspx', ajax=False)
        # if no modal, the A4J action already authenticated the session server-side.

    def consulta(self, tipo, clase, consecutivo):
        url = BASE + FORM_PATH
        gu, gh = self._req(url, ref=BASE + 'login.jspx')
        if 'formBusqueda' not in gh:
            raise SystemExit('✗ No se pudo abrir el formulario de consulta '
                             '(¿login fallido o sesión expirada?). URL: ' + gu)
        vs = self._viewstate(gh)
        sub = re.search(r"jsfcljs\(document\.forms\['formBusqueda'\],'([^,]+),", gh)
        subname = sub.group(1) if sub else 'formBusqueda:j_id275'

        data = {
            'formBusqueda': 'formBusqueda',
            'formBusqueda:tipo': tipo,
            'formBusqueda:clase': clase,
            'formBusqueda:consecutivo': consecutivo,
            'javax.faces.ViewState': vs,
            subname: subname,
        }
        _, rh = self._req(url, data, ref=url)
        return self._parse_result(rh)

    @staticmethod
    def _parse_result(h):
        pairs = re.findall(r'<span class="label">(.*?)</span></td>\s*<td>(.*?)</td>', h, re.S)
        clean = lambda s: html.unescape(re.sub(r'<[^>]+>', '', s)).strip()
        result = {}
        for k, v in pairs:
            result[clean(k).rstrip(':')] = clean(v)
        return result


def parse_cedula(raw):
    """'3-109-766273' o '3109766273' -> (tipo, clase, consecutivo) preservando ceros."""
    digits = re.sub(r'\D', '', raw)
    if len(digits) != 10:
        raise SystemExit(f'✗ Cédula jurídica inválida: "{raw}". '
                         'Debe tener 10 dígitos (ej. 3109766273 o 3-109-766273).')
    return digits[0], digits[1:4], digits[4:]


def main():
    ap = argparse.ArgumentParser(description='Consulta razón social por cédula jurídica en el RNP.')
    ap.add_argument('cedula', nargs='?', help='Cédula jurídica (ej. 3109766273 o 3-109-766273)')
    ap.add_argument('--user', help='Correo de la cuenta RNP (o env RNP_USER)')
    ap.add_argument('--pass', dest='password', help='Contraseña RNP (o env RNP_PASS)')
    args = ap.parse_args()

    cedula = args.cedula or input('Cédula jurídica: ').strip()
    tipo, clase, consecutivo = parse_cedula(cedula)

    email = args.user or os.environ.get('RNP_USER') or input('Correo RNP: ').strip()
    password = args.password or os.environ.get('RNP_PASS') or getpass.getpass('Contraseña RNP: ')

    rnp = RNP()
    print('• Iniciando sesión…', file=sys.stderr)
    rnp.login(email, password)
    print(f'• Consultando {tipo}-{clase}-{consecutivo}…', file=sys.stderr)
    res = rnp.consulta(tipo, clase, consecutivo)

    nombre = res.get('NOMBRE O RAZÓN SOCIAL') or res.get('NOMBRE O RAZON SOCIAL')
    if not nombre:
        raise SystemExit('✗ No se encontró información para esa cédula jurídica.')

    print()
    print(f'Cédula jurídica : {res.get("CEDULA JURÍDICA", f"{tipo}-{clase}-{consecutivo}")}')
    print(f'Razón social    : {nombre}')
    if res.get('ESTADO ACTUAL DE LA ENTIDAD'):
        print(f'Estado          : {res["ESTADO ACTUAL DE LA ENTIDAD"]}')
    if res.get('CITAS DE PRESENTACION'):
        print(f'Citas           : {res["CITAS DE PRESENTACION"]}')


if __name__ == '__main__':
    main()
