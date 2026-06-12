#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Muebles -> Historia de Bienes.

Uso:
    python3 rnp_historia_bienes_muebles.py BMT596
    python3 rnp_historia_bienes_muebles.py --desde-carpeta MARIA_203170516
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


TIPOS_BIEN = {
    'vehiculo': '000001',
    'vehiculos': '000001',
    'automovil': '000001',
    'motocicleta': '000001',
    'buque': '000002',
    'aeronave': '000003',
    'otros': '000005',
    'general': '000000',
}


def first_value(*values):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def normalize_tipo(value):
    key = re.sub(r'[^a-zA-Z]', '', value or '').casefold()
    return TIPOS_BIEN.get(key, '000001')


def load_assets(folder):
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
        resumen = data.get('resumen') or {}
        detalle = data.get('detalle') or {}
        numero = first_value(
            resumen.get('numero'),
            detalle.get('placa'),
            detalle.get('matricula'),
            detalle.get('serie'),
            detalle.get('vin'),
            detalle.get('motor'),
            resumen.get('identificacion'),
        )
        if numero:
            records.append({
                'tipo_bien': normalize_tipo(first_value(resumen.get('tipo'), detalle.get('tipo'), detalle.get('categoria'))),
                'numero': numero,
                'origen': resumen,
            })
    return records


def find_submit_params(h):
    match = re.search(
        r"jsfcljs\(document\.forms\['params'\],'([^']*numeroConsulta,54[^']*)'",
        h,
        re.S,
    )
    if not match:
        raise SystemExit('✗ No encontré el botón Consultar de historia de bienes.')
    return parse_jsf_params(match.group(1))


def consulta_historia_bien(rnp, record):
    url, h = open_free_query(rnp, 'Bienes Muebles', 'Historia de Bienes')
    data = {
        'params': 'params',
        'params:tipoBien': record['tipo_bien'],
        'carNumber': record['numero'],
        'javax.faces.ViewState': rnp._viewstate(h),
    }
    data.update(find_submit_params(h))
    _, result = rnp._req(url, data, ref=url)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        return load_assets(args.desde_carpeta)
    return [{
        'tipo_bien': TIPOS_BIEN[args.tipo],
        'numero': args.numero,
        'origen': None,
    }]


def main():
    ap = argparse.ArgumentParser(description='Consulta historia de bienes muebles en RNP.')
    ap.add_argument('numero', nargs='?', help='Placa, matrícula, serie o identificador del bien')
    ap.add_argument('--tipo', default='vehiculo', choices=sorted(TIPOS_BIEN), help='Tipo de bien')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'numero')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/historia_bienes_muebles' if args.desde_carpeta else 'historia_bienes_muebles')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron bienes muebles para consultar historia.')
        return

    for record in limit_records(records, args.limite):
        print(f'• Consultando historia bien mueble {record["numero"]}…', file=sys.stderr)
        h = consulta_historia_bien(rnp, record)
        txt, js, raw = save_outputs(out_dir, record['numero'], h, {
            'consulta': 'Bienes Muebles - Historia de Bienes',
            'entrada': record,
        })
        print(f'{record["numero"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
