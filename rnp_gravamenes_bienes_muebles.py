#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Muebles -> Consulta de Gravámenes.

Uso:
    python3 rnp_gravamenes_bienes_muebles.py 2017-00240448-001
    python3 rnp_gravamenes_bienes_muebles.py --desde-carpeta MARIA_203170516
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


def parse_cita(raw):
    raw = raw.strip()
    match = re.fullmatch(r'(\d+)-(\d+)-(\d+)', raw)
    if not match:
        raise SystemExit(f'✗ Cita inválida: {raw}. Ejemplo: 2017-00240448-001')
    tomo, asiento, secuencia = match.groups()
    return {'cita': raw, 'tomo': tomo, 'asiento': asiento, 'secuencia': secuencia}


def extract_citas_from_text(text):
    if re.search(r'No\s+Posee\s+Gravamen', text or '', re.I):
        return []
    citas = set()
    pattern = re.compile(
        r'Tomo:\s*(\d+)\s+Asiento:\s*(\d+)\s+Secuencia:\s*(\d+)',
        re.I,
    )
    for tomo, asiento, secuencia in pattern.findall(text or ''):
        citas.add(f'{tomo}-{asiento}-{secuencia}')
    return sorted(citas)


def load_citas(folder):
    target = os.path.join(folder, 'bienes_muebles')
    if not os.path.isdir(target):
        return []
    records = []
    for name in sorted(os.listdir(target)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(target, name)
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        detalle = data.get('detalle') or {}
        for cita in extract_citas_from_text(detalle.get('texto', '')):
            parsed = parse_cita(cita)
            parsed['origen'] = data.get('resumen') or {}
            records.append(parsed)
    seen = {}
    for record in records:
        seen[record['cita']] = record
    return list(seen.values())


def find_submit_params(h):
    match = re.search(
        r"jsfcljs\(document\.forms\['params'\],'([^']*numeroConsulta,49[^']*)'",
        h,
        re.S,
    )
    if not match:
        raise SystemExit('✗ No encontré el botón Consultar de gravámenes de bienes muebles.')
    return parse_jsf_params(match.group(1))


def consulta_gravamen_mueble(rnp, cita):
    url, h = open_free_query(rnp, 'Bienes Muebles', 'Consulta de Gravámenes')
    data = {
        'params': 'params',
        'tomo': cita['tomo'],
        'asiento': cita['asiento'],
        'secuencia': cita['secuencia'],
        'javax.faces.ViewState': rnp._viewstate(h),
    }
    data.update(find_submit_params(h))
    _, result = rnp._req(url, data, ref=url)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        return load_citas(args.desde_carpeta)
    cita = parse_cita(args.cita)
    cita['origen'] = None
    return [cita]


def main():
    ap = argparse.ArgumentParser(description='Consulta gravámenes de bienes muebles en RNP.')
    ap.add_argument('cita', nargs='?', help='Cita, ej. 2017-00240448-001')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'cita')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/gravamenes_bienes_muebles' if args.desde_carpeta else 'gravamenes_bienes_muebles')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron citas de gravámenes de bienes muebles para consultar.')
        return

    for cita in limit_records(records, args.limite):
        print(f'• Consultando gravamen bien mueble {cita["cita"]}…', file=sys.stderr)
        h = consulta_gravamen_mueble(rnp, cita)
        txt, js, raw = save_outputs(out_dir, cita['cita'], h, {
            'consulta': 'Bienes Muebles - Consulta de Gravámenes',
            'entrada': cita,
        })
        print(f'{cita["cita"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
