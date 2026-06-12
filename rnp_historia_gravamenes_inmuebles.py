#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Historia de Gravámenes.

Uso:
    python3 rnp_historia_gravamenes_inmuebles.py 2015-162095-01-0002-001
    python3 rnp_historia_gravamenes_inmuebles.py --desde-carpeta MARIA_203170516
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


def parse_cita(raw):
    raw = raw.strip()
    match = re.fullmatch(r'(\d+)-(\d+)-(\d+)-(\d+)-(\d+)', raw)
    if not match:
        raise SystemExit(f'✗ Cita inválida: {raw}. Ejemplo: 2015-162095-01-0002-001')
    tomo, asiento, consecutivo, secuencia, subsecuencia = match.groups()
    return {
        'cita': raw,
        'tomo': tomo,
        'asiento': asiento,
        'consecutivo': consecutivo,
        'secuencia': secuencia,
        'subsecuencia': subsecuencia,
    }


def extract_citas(text):
    return sorted(set(re.findall(r'\b\d{3,4}-\d{4,8}-\d{2}-\d{4}-\d{3}\b', text or '')))


def find_submit_name(h):
    match = re.search(r'<input[^>]+name="([^"]+)"[^>]+(?:value="Consultar"|type="submit")', h, re.S | re.I)
    if match:
        return match.group(1)
    match = re.search(r"<a[^>]+id=\"([^\"]+)\"[^>]+alt=\"Consultar\"", h, re.S | re.I)
    if match:
        return match.group(1)
    match = re.search(r"parameters':\{'([^']+)':'\1'\}", h, re.S)
    if match:
        return match.group(1)
    match = re.search(r"jsfcljs\(document\.forms\['params'\],'([^']*)'", h, re.S)
    if match:
        return None
    raise SystemExit('✗ No encontré el botón Consultar de historia de gravámenes.')


def consulta_historia_gravamen(rnp, cita):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Historia de Gravámenes')
    data = {
        'params': 'params',
        'tomo': cita['tomo'],
        'asiento': cita['asiento'],
        'consec': cita['consecutivo'],
        'secuencia': cita['secuencia'],
        'subSecuencia': cita['subsecuencia'],
        'javax.faces.ViewState': rnp._viewstate(h),
    }
    submit = find_submit_name(h)
    if submit:
        data[submit] = submit
    _, result = rnp._req(url, data, ref=url, ajax=True)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        records = []
        for item in finca_records_from_dir(args.desde_carpeta):
            detalle = item.get('detalle', {})
            for cita in extract_citas(detalle.get('texto', '')):
                parsed = parse_cita(cita)
                parsed['origen'] = item.get('resumen', {})
                records.append(parsed)
        seen = {}
        for record in records:
            seen[record['cita']] = record
        return list(seen.values())
    cita = parse_cita(args.cita)
    cita['origen'] = None
    return [cita]


def main():
    ap = argparse.ArgumentParser(description='Consulta historia de gravámenes de inmuebles en RNP.')
    ap.add_argument('cita', nargs='?', help='Cita, ej. 2015-162095-01-0002-001')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'cita')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/historia_gravamenes_inmuebles' if args.desde_carpeta else 'historia_gravamenes_inmuebles')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron citas para consultar historia de gravámenes de inmuebles.')
        return

    for cita in limit_records(records, args.limite):
        print(f'• Consultando historia gravamen inmueble {cita["cita"]}…', file=sys.stderr)
        h = consulta_historia_gravamen(rnp, cita)
        txt, js, raw = save_outputs(out_dir, cita['cita'], h, {
            'consulta': 'Bienes Inmuebles - Historia de Gravámenes',
            'entrada': cita,
        })
        print(f'{cita["cita"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
