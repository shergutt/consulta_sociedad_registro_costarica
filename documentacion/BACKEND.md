# Backend (FastAPI)

API REST que sirve los datos persistidos en PostgreSQL y orquesta los análisis.

## Estructura

```
backend/
├── main.py                  # App entrypoint, CORS, routers, startup
├── config.py                # Settings vía pydantic-settings
├── database.py              # SQLAlchemy engine + SessionLocal
├── auth.py                  # Hashing, sesiones, dependencias de auth
├── models.py                # 12 modelos SQLAlchemy
├── schemas.py               # 18 Pydantic models
├── requirements.txt         # Dependencias Python
├── Dockerfile               # python:3.12-slim + mmx-cli
├── alembic/                 # Migraciones
│   └── versions/
│       └── 20260612_194138_v2_shared_assets.py
├── routers/
│   ├── auth.py              # /api/login, /api/logout, /api/me
│   ├── users.py             # CRUD usuarios (admin)
│   ├── persons.py           # /api/summary, /api/persons, /api/persons/{cedula}/detail
│   ├── search.py            # /api/search (búsqueda global)
│   ├── source_files.py      # /api/source-files/{id}
│   └── analysis.py          # /api/run-analysis, /api/jobs
└── services/
    └── analysis_runner.py   # Background job runner (threads)
```

## Endpoints

### Autenticación

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/login` | No | Login retorna token Bearer |
| POST | `/api/logout` | Sí | Invalida sesión |
| GET | `/api/me` | Sí | Info del usuario actual |

### Usuarios (admin)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/users` | Admin | Listar usuarios |
| POST | `/api/users` | Admin | Crear usuario |
| DELETE | `/api/users/{user_id}` | Admin | Eliminar usuario |

### Datos

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/summary` | Sí | Estadísticas del dashboard |
| GET | `/api/persons` | Sí | Lista personas accesibles |
| GET | `/api/persons/{cedula}/detail` | Sí | Detalle completo: fincas, bienes muebles, alertas, outputs, source files |
| GET | `/api/persons/{cedula}/evidencia` | Sí | Datos de evidencia |
| GET | `/api/persons/{cedula}/fuentes` | Sí | Listado de archivos fuente |
| GET | `/api/search` | Sí | Búsqueda global (personas, fincas, bienes muebles) |
| GET | `/api/source-files/{id}` | Sí | Contenido crudo de un archivo fuente |

### Análisis (jobs)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/run-analysis` | Sí | Iniciar análisis (retorna 202) |
| GET | `/api/jobs` | Sí | Listar jobs del usuario |
| GET | `/api/jobs/{id}` | Sí | Estado y log de un job |
| DELETE | `/api/run-analysis/{id}` | Sí | Eliminar job |

## Autenticación (`auth.py`)

- **Password hashing**: `pbkdf2_hmac` (SHA-256, 100k iteraciones, salt de 16 chars)
- **Formato hash**: `{salt}${hash}`
- **Tokens**: SHA-256 de UUID v4
- **Sesiones**: expiran en 24h, limpieza manual vía `cleanup_expired_sessions()`
- **Dependencias**: `get_current_user` (requiere auth), `get_optional_user` (opcional), `require_admin`

## Jobs (`services/analysis_runner.py`)

- **In-memory**: estado en `_jobs: dict[str, dict]` con `_jobs_lock` (threading.Lock)
- **No persistente**: si el servidor se reinicia, los jobs se pierden
- **Ejecución**: `threading.Thread(target=_run_job, daemon=True)`
- **MiniMax preflight**: antes de ejecutar, llama a `mmx-cli` para autorizar
- **Subprocess**: ejecuta `build_rnp_report.py` con credenciales en environment
- **Logs**: circular buffer de 1200 líneas por job

### Flujo de un job

```
1. POST /api/run-analysis → start_analysis()
2. Validar cédula (9-12 dígitos)
3. Crear/obtener Person en DB + PersonQuery
4. Crear entrada en _jobs (status: "queued")
5. Lanzar thread
6. Thread: MiniMax preflight → autoriza?
7. Thread: subprocess build_rnp_report.py
8. Thread: capturar stdout línea por línea
9. Thread: status → "succeeded" | "failed"
```

## Configuración (`config.py`)

Todas las settings se leen de `.env` vía `pydantic-settings`:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `database_url` | PostgreSQL local | URL de conexión |
| `rnp_user` | `""` | Usuario RNP |
| `rnp_pass` | `""` | Contraseña RNP |
| `minimax_api_key` | `""` | API key MiniMax |
| `ai_model` | `minimax-m3` | Modelo de IA |
| `project_dir` | `.` | Directorio del proyecto |
| `cors_origins` | localhost:3000,8765 | Orígenes CORS |
| `session_hours` | 24 | Horas de validez de sesión |
| `require_minimax` | true | Si se requiere validación MiniMax |

## Base de datos (`database.py`)

- **Engine**: pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=3600
- **SessionLocal**: sessionmaker con autocommit=False
- **get_db()**: generator para inyección de dependencias FastAPI
