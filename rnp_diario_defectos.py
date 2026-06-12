#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Consulta al Diario de Defectos de Documentos.

Uso:
    python3 rnp_diario_defectos.py 2016-00438608-01
    python3 rnp_diario_defectos.py --desde-carpeta MARIA_203170516
"""
import argparse
import re
import sys

from rnp_extra_common import (
    add_auth_args,
    add_batch_args,
    finca_records_from_dir,
    limit_records,
    login_from_args,
    maybe_pause,
    open_free_query,
    require_direct_or_folder,
    save_outputs,
)


def parse_presentacion(raw):
    raw = raw.strip()
    match = re.fullmatch(r'(\d+)-(\d+)(?:-\d+)?', raw)
    if not match:
        raise SystemExit(f'✗ Presentación inválida: {raw}. Ejemplo: 2016-00438608-01')
    tomo, asiento = match.groups()
    return {'presentacion': raw, 'tomo': tomo, 'asiento': asiento}


def extract_presentaciones(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{5,8}-\d{2}\b', text or '')))


def find_submit_name(h):
    match = re.search(r"parameters':\{'([^']+)':'\1'\}", h, re.S)
    if match:
        return match.group(1)
    raise SystemExit('✗ No encontré el botón Consultar de diario de defectos.')


def consulta_defectos(rnp, presentacion):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Consulta al Diario de Defectos de Documentos')
    submit = find_submit_name(h)
    data = {
        'params': 'params',
        'params:tomo': presentacion['tomo'],
        'params:asiento': presentacion['asiento'],
        'javax.faces.ViewState': rnp._viewstate(h),
        submit: submit,
    }
    _, result = rnp._req(url, data, ref=url, ajax=True)
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
        seen = {}
        for record in records:
            seen[record['presentacion']] = record
        return list(seen.values())
    presentacion = parse_presentacion(args.presentacion)
    presentacion['origen'] = None
    return [presentacion]


def main():
    ap = argparse.ArgumentParser(description='Consulta diario de defectos de documentos en RNP.')
    ap.add_argument('presentacion', nargs='?', help='Presentación, ej. 2016-00438608-01')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'presentacion')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/diario_defectos' if args.desde_carpeta else 'diario_defectos')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron presentaciones para consultar diario de defectos.')
        return

    for presentacion in limit_records(records, args.limite):
        print(f'• Consultando diario de defectos {presentacion["presentacion"]}…', file=sys.stderr)
        h = consulta_defectos(rnp, presentacion)
        txt, js, raw = save_outputs(out_dir, presentacion['presentacion'], h, {
            'consulta': 'Bienes Inmuebles - Consulta al Diario de Defectos de Documentos',
            'entrada': presentacion,
        })
        print(f'{presentacion["presentacion"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
