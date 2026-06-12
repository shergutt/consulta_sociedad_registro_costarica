#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Consulta de Documento / Diario.

Uso:
    python3 rnp_documento_diario.py 2016-00438608-01
    python3 rnp_documento_diario.py --desde-carpeta MARIA_203170516
"""
import argparse
import re
import sys

from rnp_extra_common import (
    add_auth_args,
    add_batch_args,
    finca_records_from_dir,
    form_action_url,
    limit_records,
    login_from_args,
    maybe_pause,
    open_free_query,
    require_direct_or_folder,
    save_outputs,
)


def parse_presentacion(raw):
    raw = raw.strip()
    m = re.fullmatch(r'(\d+)-(\d+)-(\d+)', raw)
    if not m:
        raise SystemExit(f'✗ Presentación inválida: {raw}. Ejemplo: 2016-00438608-01')
    tomo, asiento, consecutivo = m.groups()
    return {
        'presentacion': raw,
        'tomo': tomo,
        'asiento': asiento,
        'consecutivo': consecutivo,
    }


def extract_presentaciones(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{5,8}-\d{2}\b', text or '')))


def find_submit_button(h):
    m = re.search(
        r'<a[^>]+id="(params:[^"]+)"[^>]+onclick="A4J\.AJAX\.Submit\(',
        h,
        re.S)
    if not m:
        raise SystemExit('✗ No encontré el botón Consultar del Diario.')
    return m.group(1)


def consulta_documento(rnp, presentacion):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Consulta de Documento')
    action_url = form_action_url(rnp, h, 'params')
    button = find_submit_button(h)
    _, result = rnp._req(action_url, {
        'params': 'params',
        'params:tomo': presentacion['tomo'],
        'params:asiento': presentacion['asiento'],
        'javax.faces.ViewState': rnp._viewstate(h),
        'AJAXREQUEST': 'params',
        'consec': '-1',
        button: button,
        'opid': 'null',
    }, ref=url, ajax=True)
    redirect = re.search(r'<meta name="Location" content="([^"]+)"', result)
    if redirect:
        _, result = rnp._req(rnp._abs(redirect.group(1)), ref=action_url)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        records = []
        for item in finca_records_from_dir(args.desde_carpeta):
            detalle = item.get('detalle', {})
            for presentacion in extract_presentaciones(detalle.get('texto', '')):
                parsed = parse_presentacion(presentacion)
                parsed['origen'] = item.get('resumen', {})
                records.append(parsed)
        return records
    presentacion = parse_presentacion(args.presentacion)
    presentacion['origen'] = None
    return [presentacion]


def main():
    ap = argparse.ArgumentParser(description='Consulta documentos del Diario en RNP.')
    ap.add_argument('presentacion', nargs='?', help='Presentación, ej. 2016-00438608-01')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'presentacion')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/documentos_diario' if args.desde_carpeta else 'documentos_diario')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron presentaciones para consultar.')
        return

    for presentacion in limit_records(records, args.limite):
        print(f'• Consultando documento {presentacion["presentacion"]}…', file=sys.stderr)
        h = consulta_documento(rnp, presentacion)
        txt, js, raw = save_outputs(out_dir, presentacion['presentacion'], h, {
            'consulta': 'Bienes Inmuebles - Consulta de Documento / Diario',
            'entrada': presentacion,
        })
        print(f'{presentacion["presentacion"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
