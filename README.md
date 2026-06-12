# Consulta de Sociedades — Registro Nacional de Costa Rica

Script de línea de comandos que consulta el **nombre o razón social** de una
persona jurídica costarricense en el [Registro Nacional](https://www.rnpdigital.com)
(RNP), a partir de su **cédula jurídica**.

Además de la razón social, devuelve el estado actual de la entidad y las citas de
presentación cuando están disponibles.

## ¿Cómo funciona?

La consulta gratuita del RNP requiere una cuenta registrada e iniciar sesión. El
sitio permite **una sola sesión activa por usuario**: si ya hay una abierta (por
ejemplo, en tu navegador), el script la cierra automáticamente y crea una nueva.

Internamente el script:

1. Inicia sesión en `rnpdigital.com` (manejando los tokens JSF/A4J del formulario).
2. Si detecta el modal de "sesión activa", confirma para continuar y cerrar la otra sesión.
3. Abre el formulario de consulta de persona jurídica por cédula.
4. Parsea el resultado y lo imprime de forma legible.

No depende de librerías externas: usa solo la biblioteca estándar de Python.

## Requisitos

- **Python 3** (no requiere paquetes adicionales).
- Una **cuenta registrada** en [rnpdigital.com](https://www.rnpdigital.com).

## Uso

```bash
# Pasando la cédula como argumento (pedirá credenciales si no las da)
python3 rnp_consulta.py 3109766273

# Acepta la cédula con o sin guiones
python3 rnp_consulta.py 3-109-766273 --user correo@ejemplo.com --pass MiClave

# Usando variables de entorno para las credenciales
RNP_USER=correo@ejemplo.com RNP_PASS=MiClave python3 rnp_consulta.py 3109766273
```

## Base de datos local

Para guardar los análisis completos por persona en SQLite:

```bash
python3 rnp_database.py ingest EVELIO_202830740 --cedula 202830740
python3 rnp_database.py list
python3 rnp_database.py show 202830740
```

La base por defecto es `rnp_personas.sqlite`. Guarda personas, análisis,
fincas, bienes muebles, consultas extra, alertas y los archivos crudos
(`.json`, `.txt`, `.html`, `.md`) para auditoría.

Cuando se usa el skill/orquestador `build_rnp_report.py`, la base se actualiza
automáticamente al terminar `analisis.md` si existe `rnp_database.py` en el
proyecto. Usá `--no-db` para saltar este paso o `--db RUTA` para elegir otro
archivo SQLite.

El orquestador ahora corre por defecto:

```bash
python3 ~/.codex/skills/analyze-rnp-cedula/scripts/build_rnp_report.py 202830740 --project .
```

Ese flujo consulta Bienes Inmuebles, Catastro por plano, Historia de finca,
Consulta por número de finca, Gravámenes/Hipotecas, Documentos/Diario, Diario
de Defectos, Libro de Primeras Presentaciones, Anotaciones/Trámites/Marginales,
Valores de finca, Historia de gravámenes, Bienes Muebles por identificación,
Historia de bienes muebles, Historia/Citas de presentaciones muebles y
Gravámenes de bienes muebles cuando haya citas.
Los bienes muebles se guardan en `<CARPETA_PERSONA>/bienes_muebles/` y se
ingestan en la tabla `movable_assets`. Para omitir esa consulta:

```bash
python3 ~/.codex/skills/analyze-rnp-cedula/scripts/build_rnp_report.py 202830740 --project . --no-muebles
```

Scripts manuales para profundizar sobre activos específicos cuando ya tenés el
identificador:

```bash
python3 rnp_vehiculos.py ABC123
python3 rnp_aeronaves.py --serie SERIE123
python3 rnp_buques.py --matricula MATRICULA123
```

## Dashboard local

Para explorar la base desde el navegador:

```bash
python3 rnp_dashboard.py
```

Abrí `http://127.0.0.1:8765`. El dashboard muestra métricas generales,
personas, fincas, bienes muebles, alertas, consultas extra, reporte Markdown y
archivos fuente guardados en SQLite.

El panel **IA runner minimax-m3** permite ingresar una cédula nueva desde el
navegador. El servidor local ejecuta el skill `analyze-rnp-cedula`, genera el
reporte y actualiza `rnp_personas.sqlite`; la pantalla muestra logs y refresca
la persona cuando el job termina.

El runner usa MiniMax como preflight antes de correr el skill. Puede usar
`MINIMAX_API_KEY` desde `.env` o una sesión ya configurada con `mmx auth login`.
La llave no se guarda en el código ni se devuelve por la API del dashboard.

Opciones útiles:

```bash
python3 rnp_dashboard.py --db rnp_personas.sqlite --port 8765
python3 rnp_dashboard.py --host 127.0.0.1 --port 9000
python3 rnp_dashboard.py --ai-model minimax-m3
```

Endpoints del runner:

```bash
curl -X POST http://127.0.0.1:8765/api/run-analysis \
  -H 'Content-Type: application/json' \
  -d '{"cedula":"202830740"}'

curl http://127.0.0.1:8765/api/jobs
curl http://127.0.0.1:8765/api/jobs/JOB_ID
```

Si no se indican, el script pedirá la cédula y las credenciales de forma interactiva
(la contraseña se solicita de forma oculta).

### Credenciales

Orden de prioridad para las credenciales:

1. Argumentos `--user` / `--pass`
2. Variables de entorno `$RNP_USER` / `$RNP_PASS`
3. Prompt interactivo

> **Recomendación:** usá variables de entorno o el prompt interactivo. Evitá pasar
> la contraseña con `--pass` en sistemas compartidos, ya que queda visible en el
> historial del shell y en la lista de procesos.

## Ejemplo de salida

```
• Iniciando sesión…
• Consultando 3-109-766273…

Cédula jurídica : 3-109-766273
Razón social    : EJEMPLO SOCIEDAD ANONIMA
Estado          : INSCRITA
Citas           : ...
```

## Formato de la cédula jurídica

La cédula jurídica debe tener **10 dígitos**. Se acepta con o sin guiones:

- `3109766273`
- `3-109-766273`

## Aviso

Este proyecto no está afiliado al Registro Nacional de Costa Rica. Es una
herramienta no oficial que automatiza la consulta pública disponible en el sitio
del RNP, sujeta a los términos de uso del sitio. Usalo de forma responsable.
