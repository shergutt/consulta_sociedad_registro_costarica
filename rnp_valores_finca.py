#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Valores de Finca.

Uso:
    python3 rnp_valores_finca.py 2-277083
    python3 rnp_valores_finca.py --desde-carpeta MARIA_203170516
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
    province_code_from_summary,
    require_direct_or_folder,
    save_outputs,
)


def parse_finca(raw):
    parts = re.findall(r'[0-9A-Za-z]+', raw)
    if len(parts) < 2:
        raise SystemExit(f'✗ Finca inválida: {raw}. Ejemplo: 2-277083')
    return {
        'provincia': parts[0],
        'finca': parts[1],
        'duplicado': parts[2] if len(parts) > 2 else '',
        'horizontal': parts[3] if len(parts) > 3 else '',
    }


def find_submit_params(h):
    match = re.search(
        r"jsfcljs\(document\.forms\['params'\],'([^']*numeroConsulta,18[^']*)'",
        h,
        re.S,
    )
    if not match:
        raise SystemExit('✗ No encontré el botón Consultar de valores de finca.')
    return parse_jsf_params(match.group(1))


def consulta_valores(rnp, finca):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Valores de Finca')
    data = {
        'params': 'params',
        'params:j_id268': finca['provincia'],
        'params:finca': finca['finca'],
        'params:j_id279': finca.get('duplicado', ''),
        'params:j_id308': finca.get('horizontal', ''),
        'javax.faces.ViewState': rnp._viewstate(h),
    }
    data.update(find_submit_params(h))
    _, result = rnp._req(url, data, ref=url)
    return result


def records_from_args(args):
    if args.desde_carpeta:
        out = []
        for item in finca_records_from_dir(args.desde_carpeta):
            resumen = item.get('resumen', {})
            out.append({
                'provincia': province_code_from_summary(resumen),
                'finca': str(resumen.get('numero', '')).strip(),
                'duplicado': str(resumen.get('duplicado', '')).strip(),
                'horizontal': str(resumen.get('horizontal', '')).strip(),
                'origen': resumen,
            })
        return out
    finca = parse_finca(args.finca)
    finca['origen'] = None
    return [finca]


def base_name(finca):
    parts = [finca['provincia'], finca['finca']]
    if finca.get('duplicado'):
        parts.append(finca['duplicado'])
    if finca.get('horizontal'):
        parts.append(finca['horizontal'])
    return '_'.join(parts)


def main():
    ap = argparse.ArgumentParser(description='Consulta valores de finca en RNP.')
    ap.add_argument('finca', nargs='?', help='Finca, ej. 2-277083')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'finca')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/valores_finca' if args.desde_carpeta else 'valores_finca')
    rnp = login_from_args(args)

    for finca in limit_records(records_from_args(args), args.limite):
        print(f'• Consultando valores finca {base_name(finca)}…', file=sys.stderr)
        h = consulta_valores(rnp, finca)
        txt, js, raw = save_outputs(out_dir, base_name(finca), h, {
            'consulta': 'Bienes Inmuebles - Valores de Finca',
            'entrada': finca,
        })
        print(f'{base_name(finca)}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
