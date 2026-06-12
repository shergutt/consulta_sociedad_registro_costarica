#!/usr/bin/env python3
"""
Consulta gratuita: Bienes Inmuebles -> Consulta por Número de Finca.

Uso:
    python3 rnp_finca_numero.py 2-277083-000
    python3 rnp_finca_numero.py --desde-carpeta MARIA_203170516
"""
import argparse
import re
import sys

from rnp_extra_common import (
    add_auth_args,
    add_batch_args,
    derecho_from_summary,
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
        raise SystemExit(f'✗ Finca inválida: {raw}. Ejemplo: 2-277083-000')
    return {
        'provincia': parts[0],
        'finca': parts[1],
        'duplicado': parts[2] if len(parts) > 3 else '',
        'horizontal': parts[3] if len(parts) > 4 else '',
        'derecho': parts[-1].zfill(3) if len(parts) >= 3 and parts[-1].isdigit() else '000',
    }


def find_submit_params(h):
    match = re.search(
        r"jsfcljs\(document\.forms\['params'\],'([^']*numeroConsulta,13[^']*)'",
        h,
        re.S,
    )
    if not match:
        raise SystemExit('✗ No encontré el botón Consultar de finca por número.')
    return parse_jsf_params(match.group(1))


def consulta_finca(rnp, finca):
    url, h = open_free_query(rnp, 'Bienes Inmuebles', 'Consulta por Número de Finca')
    data = {
        'params': 'params',
        'params:j_id268': finca['provincia'],
        'params:finca': finca['finca'],
        'params:j_id279': finca.get('duplicado', ''),
        'params:j_id308': finca.get('horizontal', ''),
        'params:j_id313': finca.get('derecho', ''),
        'params:argus': '',
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
                'derecho': derecho_from_summary(resumen),
                'origen': resumen,
            })
        return out
    finca = parse_finca(args.finca)
    finca['origen'] = None
    return [finca]


def base_name(finca):
    return f'{finca["provincia"]}_{finca["finca"]}_{finca.get("derecho", "")}'


def main():
    ap = argparse.ArgumentParser(description='Consulta finca por número en RNP.')
    ap.add_argument('finca', nargs='?', help='Finca, ej. 2-277083-000')
    add_batch_args(ap)
    add_auth_args(ap)
    args = ap.parse_args()
    require_direct_or_folder(args, 'finca')

    out_dir = args.salida or (
        f'{args.desde_carpeta}/finca_numero' if args.desde_carpeta else 'finca_numero')
    rnp = login_from_args(args)

    for finca in limit_records(records_from_args(args), args.limite):
        print(f'• Consultando finca por número {base_name(finca)}…', file=sys.stderr)
        h = consulta_finca(rnp, finca)
        txt, js, raw = save_outputs(out_dir, base_name(finca), h, {
            'consulta': 'Bienes Inmuebles - Consulta por Número de Finca',
            'entrada': finca,
        })
        print(f'{base_name(finca)}: {txt} | {js} | {raw}')
        maybe_pause(args.pausa)


if __name__ == '__main__':
    main()
