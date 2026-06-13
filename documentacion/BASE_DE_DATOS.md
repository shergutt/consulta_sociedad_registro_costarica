# Base de Datos (PostgreSQL)

Base de datos compartida `rnp_intelligence` en PostgreSQL. Migración desde SQLite (por usuario) hacia un esquema centralizado con control de acceso.

## Tablas (12)

### `users`

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `id` | INTEGER | PK, autoincrement |
| `username` | VARCHAR(255) | NOT NULL, UNIQUE |
| `password_hash` | VARCHAR(255) | NOT NULL |
| `role` | VARCHAR(20) | NOT NULL, DEFAULT 'user', CHECK (IN 'admin','user') |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

Relaciones: `sessions`, `person_queries`, `query_runs`

### `sessions`

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `token` | VARCHAR(255) | PK |
| `user_id` | INTEGER | FK → users.id (CASCADE), NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `expires_at` | TIMESTAMPTZ | NOT NULL |

Índices: `idx_sessions_user`, `idx_sessions_expires`

### `persons`

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `id` | INTEGER | PK, autoincrement |
| `cedula` | VARCHAR(20) | NOT NULL, UNIQUE |
| `nombre` | VARCHAR(500) | |
| `first_name` | VARCHAR(255) | |
| `latest_folder_path` | TEXT | |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

Relaciones: `fincas`, `movable_assets`, `query_runs`, `person_queries`

### `person_queries` (junction)

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `id` | INTEGER | PK, autoincrement |
| `person_id` | INTEGER | FK → persons.id (CASCADE), NOT NULL |
| `user_id` | INTEGER | FK → users.id (SET NULL) |
| `queried_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Función**: Control de acceso — un usuario ve solo las persons para las que tiene registro aquí.
Índices: `idx_person_queries_person`, `idx_person_queries_user`

### `query_runs`

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `id` | INTEGER | PK, autoincrement |
| `person_id` | INTEGER | FK → persons.id (CASCADE), NOT NULL |
| `triggered_by_user_id` | INTEGER | FK → users.id (SET NULL) |
| `folder_path` | TEXT | NOT NULL |
| `report_path` | TEXT | |
| `report_markdown` | TEXT | |
| `finca_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `alert_count` | INTEGER | NOT NULL, DEFAULT 0 |
| `output_counts_json` | TEXT | NOT NULL, DEFAULT '{}' |
| `ran_at` | TIMESTAMPTZ | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

UK: `(person_id, folder_path)`
Índices: `idx_query_runs_person`

### `fincas`

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `id` | INTEGER | PK, autoincrement |
| `persona_id` | INTEGER | FK → persons.id (CASCADE), NOT NULL |
| `query_run_id` | INTEGER | FK → query_runs.id (RESTRICT), NOT NULL |
| `index_no` | INTEGER | |
| `provincia` | VARCHAR(255) | |
| `provincia_codigo` | VARCHAR(20) | |
| `numero` | VARCHAR(50) | |
| `derecho` | VARCHAR(50) | |
| `duplicado` | VARCHAR(50) | |
| `horizontal` | VARCHAR(50) | |
| `matricula` | VARCHAR(100) | |
| `naturaleza` | TEXT | |
| `ubicacion` | TEXT | |
| `zona_catastrada` | VARCHAR(255) | |
| `medida` | TEXT | |
| `plano` | VARCHAR(100) | |
| `antecedentes` | TEXT | |
| `identificador_predial` | VARCHAR(100) | |
| `valor_fiscal_text` | VARCHAR(255) | |
| `valor_fiscal_num` | FLOAT | |
| `propietario` | TEXT | |
| `anotaciones` | TEXT | |
| `gravamenes` | TEXT | |
| `resumen_json` | TEXT | NOT NULL |
| `detalle_json` | TEXT | NOT NULL |
| `texto` | TEXT | |
| `source_json` | TEXT | |
| `source_txt` | TEXT | |
| `source_html` | TEXT | |

UK: `(persona_id, numero, derecho, plano)`
Índices: `idx_fincas_persona`, `idx_fincas_numero`, `idx_fincas_plano`

### `movable_assets`

| Columna | Tipo | Restricciones |
|---------|------|--------------|
| `id` | INTEGER | PK, autoincrement |
| `persona_id` | INTEGER | FK → persons.id (CASCADE), NOT NULL |
| `query_run_id` | INTEGER | FK → query_runs.id (RESTRICT), NOT NULL |
| `index_no` | INTEGER | |
| `asset_type` | VARCHAR(50) | NOT NULL, DEFAULT 'bien_mueble' |
| `identificacion` | VARCHAR(255) | |
| `nombre` | VARCHAR(500) | |
| ... | ... | marca, modelo, year, color, serie, vin, motor, chasis, placa, matricula, propietario, etc. |

UK: `(persona_id, placa, vin, serie, motor, chasis)`
Índices: `idx_movable_persona`, `idx_movable_placa`, `idx_movable_vin`

### `query_outputs`

Outputs de cada consulta hecha durante un analysis run (historia finca, gravamenes, catastro, etc.)

| Columna | Tipo |
|---------|------|
| `id` | PK |
| `query_run_id` | FK → query_runs.id (CASCADE) |
| `query_type` | VARCHAR(100), NOT NULL |
| `lookup_key` | VARCHAR(255), NOT NULL |
| `consulta` | TEXT |
| `entrada_json`, `origen_json`, `payload_json` | TEXT |
| `texto` | TEXT |
| `source_json`, `source_txt`, `source_html` | TEXT |

Índices: `idx_query_outputs_run`, `idx_query_outputs_type_key`

### `finca_query_outputs` (junction)

Asocia query_outputs a fincas específicas.

| Columna | Tipo |
|---------|------|
| `finca_id` | FK → fincas.id (CASCADE), PK |
| `query_output_id` | FK → query_outputs.id (CASCADE), PK |
| `relation` | VARCHAR(50), NOT NULL, PK |

### `alerts`

Alertas generadas durante el análisis (hipotecas, servidumbres, bajo valor, etc.)

| Columna | Tipo |
|---------|------|
| `id` | PK |
| `query_run_id` | FK → query_runs.id (CASCADE) |
| `finca_id` | FK → fincas.id (SET NULL) |
| `severity` | VARCHAR(20), NOT NULL |
| `label` | VARCHAR(500) |
| `message` | TEXT, NOT NULL |
| `source` | VARCHAR(255), NOT NULL |

Índice: `idx_alerts_run`

### `source_files`

Archivos fuente (JSON, HTML, TXT) de cada query run, con deduplicación por SHA-256.

| Columna | Tipo |
|---------|------|
| `id` | PK |
| `query_run_id` | FK → query_runs.id (CASCADE) |
| `relative_path` | TEXT, NOT NULL |
| `file_type` | VARCHAR(20), NOT NULL |
| `size_bytes` | INTEGER, NOT NULL |
| `sha256` | VARCHAR(64), NOT NULL |
| `content_text` | TEXT |

UK: `(query_run_id, relative_path)`
Índice: `idx_source_files_run`

## Diagrama de relaciones

```
users ──< sessions
  │
  └──< person_queries >── persons ──< fincas
                                     │    └──< finca_query_outputs >── query_outputs
                                     │                                       │
                                     └──< query_runs ──< alerts              │
                                              │                              │
                                              └──< source_files              │
                                                                             │
                                     movable_assets ──< persons              │
                                              │                              │
                                              └──< query_runs                │
                                                                             │
                                     query_runs ──< query_outputs ───────────┘
```

## Estrategia de índices

- Índices en todas las FK para joins eficientes
- UKs compuestas para evitar duplicados naturales (fincas, muebles, query_runs, source_files)
- Índices en columnas de búsqueda frecuente: `numero`, `plano`, `placa`, `vin`
