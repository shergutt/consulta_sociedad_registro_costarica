# Scrapers Python

Todos los scrapers usan **exclusivamente la standard library de Python** (sin requests, BeautifulSoup, Selenium). Manejan manualmente:

- JSF (`javax.faces.ViewState`) y A4J tokens
- Cookies de sesión del RNP
- Cierre de sesiones existentes (el RNP solo permite 1 sesión activa por usuario)
- Parsing de HTML con `html.parser`
- POST con `urllib.request`

## Archivos raíz (27 scripts)

### Core / Base

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `rnp_indice_documentos.py` | ~250 | Clase base `RNPIndiceDocumentos`: login, session management, navegación de índices |
| `rnp_extra_common.py` | ~200 | Helpers compartidos: `clean()`, `safe_name()`, `login_from_args()`, `open_free_query()`, `save_outputs()`, batch processing |

### Consultas principales

| Archivo | Propósito |
|---------|-----------|
| `rnp_consulta.py` | CLI principal — consulta simple de persona jurídica por nombre |
| `rnp_persona_bienes_inmuebles.py` | Persona → bienes inmuebles (fincas). El scraper más grande, clase RNP standalone |
| `rnp_persona_bienes_muebles.py` | Persona → bienes muebles |

### Vehículos, Aeronaves, Buques

| Archivo | Propósito |
|---------|-----------|
| `rnp_vehiculos.py` | Búsqueda de vehículos por placa, chasis, motor, VIN, serie |
| `rnp_aeronaves.py` | Búsqueda de aeronaves por serial o registro |
| `rnp_buques.py` | Búsqueda de buques por registro, casco, motor, nombre, serie |

### Catastro y Fincas

| Archivo | Propósito |
|---------|-----------|
| `rnp_catastro_plano.py` | Consulta de plano catastral por número de plano |
| `rnp_finca_numero.py` | Búsqueda de finca por número |
| `rnp_historia_finca.py` | Historial completo de una finca |
| `rnp_valores_finca.py` | Valuación fiscal de finca |

### Gravámenes e Hipotecas

| Archivo | Propósito |
|---------|-----------|
| `rnp_gravamen_hipoteca.py` | Consulta de gravámenes e hipotecas sobre inmuebles |
| `rnp_historia_gravamenes_inmuebles.py` | Historial de gravámenes sobre inmuebles |
| `rnp_gravamenes_bienes_muebles.py` | Gravámenes sobre bienes muebles |
| `rnp_historia_bienes_muebles.py` | Historial de bienes muebles |
| `rnp_historia_presentaciones_muebles.py` | Historial de presentaciones de muebles |
| `rnp_citas_presentacion_muebles.py` | Citas de presentación de bienes muebles |

### Anotaciones, Trámites y Diario

| Archivo | Propósito |
|---------|-----------|
| `rnp_anotaciones_tramites.py` | Anotaciones, trámites y marginales |
| `rnp_documento_diario.py` | Consulta de documento/diario |
| `rnp_diario_defectos.py` | Diario de defectos |
| `rnp_primeras_presentaciones.py` | Primeras presentaciones (por nombre de persona) |
| `rnp_indice_documentos.py` | Índice general de documentos |

### Ingesta

| Archivo | Propósito |
|---------|-----------|
| `rnp_ingest_pg.py` | Script raíz que ingesta los folders de análisis a PostgreSQL |

## Patrón común de los scrapers

```python
# 1. Login
session = login(user, pass)

# 2. Obtener formulario JSF
response = session.get(url)
viewstate = extraer_viewstate(response)

# 3. Enviar consulta con parámetros A4J
payload = construir_payload(datos_busqueda, viewstate)
response = session.post(url, data=payload)

# 4. Parsear resultado HTML
soup = BeautifulSoup(response.text, 'html.parser')
resultados = extraer_datos(soup)

# 5. Guardar outputs
save_outputs(resultados, output_dir, formatos=['json', 'html', 'txt'])
```

## Formato de salida

Cada scraper guarda resultados en 3 formatos:
- **JSON**: datos estructurados parseados
- **HTML**: respuesta HTML cruda del servidor
- **TXT**: representación en texto plano
