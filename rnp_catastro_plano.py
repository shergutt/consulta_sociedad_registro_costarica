#!/usr/bin/env python3
"""
Consulta gratuita: Catastro -> Consulta de Plano.

Uso:
    python3 rnp_catastro_plano.py A-2081763-2018
    python3 rnp_catastro_plano.py --desde-carpeta MARIA_203170516
"""
import argparse
import re
import sys

from rnp_extra_common import (
    add_auth_args,
    add_batch_args,
    clean,
    finca_records_from_dir,
    limit_records,
    login_from_args,
    maybe_pause,
    open_free_query,
    require_direct_or_folder,
    save_outputs,
    safe_name,
)

PROVINCIAS_PLANO = {
    'SJ': '1',
    'S': '1',
    'A': '2',
    'C': '3',
    'H': '4',
    'G': '5',
    'P': '6',
    'L': '7',
}


def parse_plano(raw):
    raw = raw.strip().upper()
    m = re.fullmatch(r'([A-Z]{1,2})-?([0-9]+)-?([0-9]{4})', raw)
    if not m:
        raise SystemExit(f'✗ Plano inválido: {raw}. Ejemplo: A-2081763-2018')
    prefix, numero, year = m.groups()
    if prefix not in PROVINCIAS_PLANO:
        raise SystemExit(f'✗ No sé mapear la provincia del plano: {prefix}')
    return {
        'plano': f'{prefix}-{numero}-{year}',
        'provincia': PROVINCIAS_PLANO[prefix],
        'numero': numero,
        'anio': year,
    }


def find_onchange_param(h):
    m = re.search(
        r"A4J\.AJAX\.Submit\('formBusqueda'.*?'parameters':\{'([^']+)':'([^']+)'\}",
        h,
        re.S)
    if not m:
        raise SystemExit('✗ No encontré el parámetro AJAX del selector de tipo de búsqueda.')
    return m.group(1), m.group(2)


def find_submit_button(h):
    m = re.search(
        r'<a[^>]+id="(formBusqueda:[^"]+)"[^>]+onclick="A4J\.AJAX\.Submit\(',
        h,
        re.S)
    if not m:
        raise SystemExit('✗ No encontré el botón Consultar del formulario de catastro.')
    return m.group(1)


def consulta_plano(rnp, plano):
    url, h = open_free_query(rnp, 'Catastro', 'Consulta de Plano')
    ajax_name, ajax_value = find_onchange_param(h)
    _, selected = rnp._req(url, {
        'formBusqueda': 'formBusqueda',
        'formBusqueda:j_id268': 'P',
        'javax.faces.ViewState': rnp._viewstate(h),
        'AJAXREQUEST': 'formBusqueda',
        ajax_name: ajax_value,
    }, ref=url, ajax=True)

    button = find_submit_button(selected)
    _, result = rnp._req(url, {
        'formBusqueda': 'formBusqueda',
        'formBusqueda:j_id268': 'P',
        'formBusqueda:j_id288': plano['provincia'],
        'formBusqueda:j_id297': plano['numero'],
        'formBusqueda:j_id299': plano['anio'],
        'javax.faces.ViewState': rnp._viewstate(selected),
        'AJAXREQUEST': 'formBusqueda',
        button: button,
    }, ref=url, ajax=True)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        records = []
        for item in finca_records_from_dir(args.desde_carpeta):
            plano = item.get('detalle', {}).get('plano')
            if plano:
                records.append({'plano': plano, 'origen': item})
        return records
    return [{'plano': args.plano, 'origen': None}]


def main():
    ap = argparse.ArgumentParser(description='Consulta planos catastrados en RNP.')
    ap.add_argument('plano', nargs='?', help='Plano, ej. A-2081763-2018')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'plano')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/catastro_planos' if args.desde_carpeta else 'catastro_planos')
    rnp = login_from_args(args)

    for record in limit_records(records_from_args(args), args.limite):
        plano = parse_plano(record['plano'])
        print(f'• Consultando plano {plano["plano"]}…', file=sys.stderr)
        h = consulta_plano(rnp, plano)
        txt, js, raw = save_outputs(out_dir, plano['plano'], h, {
            'consulta': 'Catastro - Consulta de Plano',
            'entrada': plano,
            'origen': record['origen'].get('resumen') if record['origen'] else None,
        })
        print(f'{plano["plano"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
