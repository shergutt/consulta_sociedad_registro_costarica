#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Muebles -> Consulta por Citas de Presentación.

Uso:
    python3 rnp_citas_presentacion_muebles.py 2017-00240448
    python3 rnp_citas_presentacion_muebles.py --desde-carpeta MARIA_203170516
"""
import argparse
import json
import os
import re
import sys

from rnp_extra_common import (
    add_auth_args,
    add_batch_args,
    limit_records,
    login_from_args,
    maybe_pause,
    open_free_query,
    parse_jsf_params,
    require_direct_or_folder,
    save_outputs,
)


def parse_presentacion(raw):
    raw = raw.strip()
    match = re.fullmatch(r'(\d+)-(\d+)(?:-\d+)?', raw)
    if not match:
        raise SystemExit(f'✗ Presentación inválida: {raw}. Ejemplo: 2017-00240448')
    tomo, asiento = match.groups()
    return {'presentacion': raw, 'tomo': tomo, 'asiento': asiento}


def extract_presentaciones(text):
    records = set()
    pattern = re.compile(r'Citas de Inscripci[oó]n:\s*Tomo:\s*(\d+)\s+Asiento:\s*(\d+)\s+Secuencia:\s*(\d+)', re.I)
    for tomo, asiento, secuencia in pattern.findall(text or ''):
        records.add(f'{tomo}-{asiento}-{secuencia}')
    return sorted(records)


def load_presentaciones(folder):
    target = os.path.join(folder, 'bienes_muebles')
    if not os.path.isdir(target):
        return []
    out = []
    for name in sorted(os.listdir(target)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(target, name)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for presentacion in extract_presentaciones((data.get('detalle') or {}).get('texto', '')):
            record = parse_presentacion(presentacion)
            record['origen'] = data.get('resumen') or {}
            out.append(record)
    seen = {}
    for record in out:
        seen[record['presentacion']] = record
    return list(seen.values())


def find_submit_params(h):
    match = re.search(
        r"jsfcljs\(document\.forms\['params'\],'([^']*numeroConsulta,60[^']*)'",
        h,
        re.S,
    )
    if not match:
        raise SystemExit('✗ No encontré el botón Consultar de citas de presentación muebles.')
    return parse_jsf_params(match.group(1))


def consulta_cita_presentacion(rnp, record):
    url, h = open_free_query(rnp, 'Bienes Muebles', 'Consulta por Citas de Presentación')
    data = {
        'params': 'params',
        'tomo': record['tomo'],
        'asiento': record['asiento'],
        'javax.faces.ViewState': rnp._viewstate(h),
    }
    data.update(find_submit_params(h))
    _, result = rnp._req(url, data, ref=url)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        return load_presentaciones(args.desde_carpeta)
    record = parse_presentacion(args.presentacion)
    record['origen'] = None
    return [record]


def main():
    ap = argparse.ArgumentParser(description='Consulta citas de presentación de bienes muebles en RNP.')
    ap.add_argument('presentacion', nargs='?', help='Presentación, ej. 2017-00240448')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'presentacion')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/citas_presentacion_muebles' if args.desde_carpeta else 'citas_presentacion_muebles')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron presentaciones de bienes muebles para consultar.')
        return

    for record in limit_records(records, args.limite):
        print(f'• Consultando cita presentación mueble {record["presentacion"]}…', file=sys.stderr)
        h = consulta_cita_presentacion(rnp, record)
        txt, js, raw = save_outputs(out_dir, record['presentacion'], h, {
            'consulta': 'Bienes Muebles - Consulta por Citas de Presentación',
            'entrada': record,
        })
        print(f'{record["presentacion"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
