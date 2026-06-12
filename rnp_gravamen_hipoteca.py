#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Consulta de Gravamenes e Hipotecas.

Uso:
    python3 rnp_gravamen_hipoteca.py 2015-162095-01-0002-001
    python3 rnp_gravamen_hipoteca.py --desde-carpeta MARIA_203170516
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
    parse_jsf_params,
    require_direct_or_folder,
    save_outputs,
)


def parse_cita(raw):
    raw = raw.strip()
    m = re.fullmatch(r'(\d+)-(\d+)-(\d+)-(\d+)-(\d+)', raw)
    if not m:
        raise SystemExit(f'✗ Cita inválida: {raw}. Ejemplo: 2015-162095-01-0002-001')
    tomo, asiento, consecutivo, secuencia, subsecuencia = m.groups()
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


def find_submit_params(h):
    m = re.search(
        r"jsfcljs\(document\.forms\['params'\],'([^']*sourcePage,inmuebles_consultagravhipotecas\.jsp[^']*)'",
        h,
        re.S)
    if not m:
        raise SystemExit('✗ No encontré el botón Consultar de gravámenes/hipotecas.')
    return parse_jsf_params(m.group(1))


def consulta_gravamen(rnp, cita):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Consulta de Gravámenes e Hipotecas')
    data = {
        'params': 'params',
        'params:tomo': cita['tomo'],
        'params:asiento': cita['asiento'],
        'params:consecutivo': cita['consecutivo'],
        'params:secuencia': cita['secuencia'],
        'params:subsecuencia': cita['subsecuencia'],
        'javax.faces.ViewState': rnp._viewstate(h),
    }
    data.update(find_submit_params(h))
    _, result = rnp._req(url, data, ref=url)
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
        return records
    cita = parse_cita(args.cita)
    cita['origen'] = None
    return [cita]


def main():
    ap = argparse.ArgumentParser(description='Consulta gravámenes e hipotecas en RNP.')
    ap.add_argument('cita', nargs='?', help='Cita, ej. 2015-162095-01-0002-001')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'cita')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/gravamenes_hipotecas' if args.desde_carpeta else 'gravamenes_hipotecas')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron citas de gravámenes/hipotecas para consultar.')
        return

    for cita in limit_records(records, args.limite):
        print(f'• Consultando gravamen/hipoteca {cita["cita"]}…', file=sys.stderr)
        h = consulta_gravamen(rnp, cita)
        txt, js, raw = save_outputs(out_dir, cita['cita'], h, {
            'consulta': 'Bienes Inmuebles - Consulta de Gravámenes e Hipotecas',
            'entrada': cita,
        })
        print(f'{cita["cita"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
