#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Consulta Libro de Primeras Presentaciones.

Uso:
    python3 rnp_primeras_presentaciones.py "MARIA AZUCENA RAMIREZ ARIAS"
    python3 rnp_primeras_presentaciones.py --desde-carpeta MARIA_203170516
"""
import argparse
import sys

from rnp_extra_common import (
    add_auth_args,
    add_batch_args,
    finca_records_from_dir,
    limit_records,
    login_from_args,
    maybe_pause,
    open_free_query,
    safe_name,
    save_outputs,
)


def names_from_folder(folder):
    names = []
    for item in finca_records_from_dir(folder):
        detalle = item.get('detalle', {})
        resumen = item.get('resumen', {})
        for value in (detalle.get('propietario'), resumen.get('nombre')):
            if value and value not in names:
                names.append(value)
    return names


def consulta_primeras(rnp, nombre, tipo):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Consulta Libro de Primeras Presentaciones')
    data = {
        'formBusqueda': 'formBusqueda',
        'formBusqueda:j_id268': tipo,
        'formBusqueda:j_id273': nombre,
        'formBusqueda:j_id278': 'formBusqueda:j_id278',
        'javax.faces.ViewState': rnp._viewstate(h),
        'AJAXREQUEST': 'formBusqueda',
    }
    _, result = rnp._req(url, data, ref=url, ajax=True)
    return result


def records_from_args(args):
    tipo = '1' if args.juridico else '2'
    if args.desde_carpeta:
        return [{'nombre': name, 'tipo': tipo, 'origen': args.desde_carpeta} for name in names_from_folder(args.desde_carpeta)]
    if not args.nombre:
        raise SystemExit('✗ Indique nombre o use --desde-carpeta DIR.')
    return [{'nombre': args.nombre, 'tipo': tipo, 'origen': None}]


def main():
    ap = argparse.ArgumentParser(description='Consulta libro de primeras presentaciones en RNP.')
    ap.add_argument('nombre', nargs='?', help='Nombre físico o jurídico')
    ap.add_argument('--juridico', action='store_true', help='Consultar como nombre jurídico')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()

    out_dir = args.salida or (
        f'{args.desde_carpeta}/primeras_presentaciones' if args.desde_carpeta else 'primeras_presentaciones')
    rnp = login_from_args(args)

    records = records_from_args(args)
    if not records:
        print('No se encontraron nombres para consultar primeras presentaciones.')
        return

    for record in limit_records(records, args.limite):
        print(f'• Consultando primeras presentaciones {record["nombre"]}…', file=sys.stderr)
        h = consulta_primeras(rnp, record['nombre'], record['tipo'])
        base = f'{record["tipo"]}_{safe_name(record["nombre"])}'
        txt, js, raw = save_outputs(out_dir, base, h, {
            'consulta': 'Bienes Inmuebles - Consulta Libro de Primeras Presentaciones',
            'entrada': record,
        })
        print(f'{record["nombre"]}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
