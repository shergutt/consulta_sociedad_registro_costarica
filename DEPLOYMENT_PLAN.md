# Deployment Plan: RNP Intelligence Desk

## Architecture Overview

```
┌─────────────────┐     rewrites /api/*     ┌──────────────────────────────┐
│   Vercel (CDN)  │ ──────────────────────> │  VPS HOST         │
│                 │                         │                              │
│  dashboard/     │                         │  ┌────────────────────────┐  │
│  index.html     │                         │  │ Python API (FastAPI)   │  │
│  app.js         │                         │  │ Port 8000              │  │
│  styles.css     │                         │  └──────────┬─────────────┘  │
│                 │                         │             │                │
└─────────────────┘                         │  ┌──────────▼─────────────┐  │
                                            │  │ PostgreSQL             │  │
                                            │  │ Port 8081              │  │
                                             │  │ USER@HOST              │  │
                                            │  └────────────────────────┘  │
                                            └──────────────────────────────┘
```

## Phase 1: Security (Do First)

### 1.1 Rotate exposed secrets

The `.env` file is tracked in git with live credentials. Rotate ALL of these immediately:

- `RNP_USER` / `RNP_PASS` - Change password on rnpdigital.com
- `MINIMAX_API_KEY` - Regenerate key on MiniMax dashboard

### 1.2 Remove secrets from git history

```bash
# Add .env to .gitignore (already present? verify)
echo ".env" >> .gitignore
git rm --cached .env
git commit -m "Remove .env from tracking"

# Optionally purge from history with git-filter-repo
pip install git-filter-repo
git filter-repo --invert-paths --path .env
```

### 1.3 Set secrets per platform

| Secret | Vercel | VPS |
|--------|--------|-----|
| `RNP_USER` | Environment variable | `.env` file on server |
| `RNP_PASS` | Environment variable | `.env` file on server |
| `MINIMAX_API_KEY` | Environment variable | `.env` file on server |
| `DATABASE_URL` | Not needed (frontend only) | `postgresql://USER:PASS@HOST:PORT/DBNAME` |

---

## Phase 2: Database (PostgreSQL v2)

### 2.1 Estado actual

PostgreSQL es la única base. SQLite legacy (`rnp_personas.sqlite`,
`rnp_database.py`, `rnp_dashboard.py`) eliminado; sólo queda
`backend/migrate_data.py` para migrar un backup SQLite antiguo si existiera.

### 2.2 Esquema v2 (`backend/models.py` + `backend/alembic/versions/`)

| Tabla | Notas |
|-------|-------|
| `users` | Auth con PBKDF2 |
| `sessions` | Tokens con expiración |
| `persons` | UNIQUE por `cedula`, compartida entre usuarios |
| `person_queries` | Auditoría: quién buscó a quién y cuándo |
| `query_runs` | Una corrida por `(persona, folder_path)`, UPSERT en re-ejecución |
| `fincas` | Compartida por persona; UNIQUE en `(persona_id, numero, derecho, plano)` |
| `movable_assets` | Compartida por persona; UNIQUE en `(persona_id, placa, vin, serie, motor, chasis)` |
| `query_outputs` | Salidas crudas, por corrida |
| `finca_query_outputs` | N:M finca ↔ query_output |
| `alerts` | Por corrida, opcionalmente apuntando a una finca |
| `source_files` | Por corrida, con `sha256` |

### 2.3 Migración Alembic

```bash
cd backend
alembic upgrade head    # crea las 11 tablas si la BD está vacía
```

La migración inicial `20260612_194138_v2_shared_assets.py` hace DROP+CASCADE
de las tablas v1 y CREATE de las v2. Es idempotente contra v1.

### 2.4 Migración de datos SQLite legacy

Si tenés un `rnp_personas.sqlite` de antes:

```bash
cd backend
DATABASE_URL=... python migrate_data.py
```

El script conserva solo la corrida más reciente por persona (decisión
documentada en el plan de v2), descarta `sessions` huérfanas, y reinicia las
secuencias al `MAX(id)` correspondiente.

---

## Phase 3: Backend Rewrite (Python HTTP → FastAPI on VPS)

### 3.1 Why FastAPI

- Replaces the raw `BaseHTTPRequestHandler` with proper routing
- Auto-generates OpenAPI docs at `/docs`
- Native async support for long-running analysis jobs
- Pydantic validation for request/response schemas
- CORS middleware for Vercel frontend
- Production-grade with uvicorn

### 3.2 Project structure for VPS deployment

```
backend/
├── main.py              # FastAPI app entry point
├── config.py            # Settings via pydantic-settings
├── database.py          # SQLAlchemy engine + session
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response schemas
├── auth.py              # Login, session, password hashing
├── routers/
│   ├── auth.py          # POST /api/login, /api/logout, GET /api/me
│   ├── users.py         # CRUD /api/users (admin only)
│   ├── persons.py       # GET /api/persons, /api/persons/{cedula}
│   ├── summary.py       # GET /api/summary
│   ├── search.py        # GET /api/search
│   ├── analysis.py      # POST /api/run-analysis, GET /api/jobs
│   └── source_files.py  # GET /api/source-files/{id}
├── services/
│   ├── analysis_runner.py  # Background job logic
│   └── minimax.py          # MiniMax preflight
├── alembic/             # Database migrations
├── alembic.ini
├── requirements.txt
├── .env                 # Server-side secrets (NOT in git)
└── Dockerfile
```

### 3.3 Key changes from current code

| Current (`rnp_dashboard.py`, eliminado) | New (FastAPI) |
|------------------------------|---------------|
| `BaseHTTPRequestHandler` | FastAPI routers |
| Manual JSON parsing | Pydantic models |
| `threading.Thread` for jobs | `BackgroundTasks` or Celery |
| `sqlite3.connect()` | SQLAlchemy `AsyncSession` |
| Manual auth header parsing | FastAPI `Depends()` with OAuth2 bearer |
| No CORS | `CORSMiddleware` configured for Vercel domain |

### 3.4 CORS configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-vercel-domain.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3.5 Requirements file

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
alembic>=1.13.0
pydantic-settings>=2.0.0
python-multipart>=0.0.9
```

### 3.6 Dockerfile for VPS

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN alembic upgrade head

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.7 Run on VPS

```bash
# Option A: Docker
docker build -t rnp-api .
docker run -d --name rnp-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  rnp-api

# Option B: systemd service
# /etc/systemd/system/rnp-api.service
[Unit]
Description=RNP Intelligence API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/rnp-api
EnvironmentFile=/opt/rnp-api/.env
ExecStart=/opt/rnp-api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3.8 Nginx reverse proxy (recommended)

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

---

## Phase 4: Frontend Deployment (Vercel)

### 4.1 Prepare frontend for Vercel

The `dashboard/` folder already contains static HTML/JS/CSS. Minimal changes needed.

#### Update API base URL in `app.js`

Currently all API calls use relative paths like `/api/login`. With Vercel rewrites, **no changes needed** to `app.js` - the rewrites handle the proxying.

### 4.2 Create `vercel.json`

```json
{
  "buildCommand": "",
  "outputDirectory": "dashboard",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://api.yourdomain.com/api/:path*"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

If you don't have a custom domain for the API, use the VPS IP directly (requires CORS on backend):

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://HOST:8000/api/:path*"
    }
  ]
}
```

### 4.3 Deploy to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# From project root
vercel --prod
```

Or connect the GitHub repo to Vercel for automatic deployments.

### 4.4 Vercel project settings

| Setting | Value |
|---------|-------|
| Framework Preset | `Other` |
| Output Directory | `dashboard` |
| Build Command | (empty) |
| Root Directory | `/` (project root) |

---

## Phase 5: RNP Scraping Scripts

The `rnp_*.py` scripts (consulta, historia_finca, etc.) run locally and write JSON/TXT/HTML to person folders. These stay on the VPS or your local machine.

### 5.1 Ingesta al backend (PostgreSQL v2)

La ingesta de carpetas se hace con `backend/rnp_ingest_pg.py`, llamado por
el orquestador `build_rnp_report.py` o por CLI:

```bash
cd backend
DATABASE_URL=... python rnp_ingest_pg.py <carpeta> --user-id 7 --cedula 203170516
```

`ingest_folder()` hace UPSERT por claves naturales en `fincas` y
`movable_assets`, registra la búsqueda en `person_queries`, y crea un
`query_run` por `(person_id, folder_path)`.

### 5.2 Workflow after deployment

```
1. Run RNP scraping scripts locally or on VPS → generates JSON/TXT/HTML folders
2. Run `python rnp_ingest_pg.py <folder> --cedula X` → writes to PostgreSQL v2
3. Vercel frontend reads data via FastAPI on VPS
```

---

## Phase 6: Checklist

### Pre-deployment
- [ ] Rotate RNP credentials and MiniMax API key
- [ ] Remove `.env` from git tracking
- [ ] Create PostgreSQL database `rnp_intelligence` on VPS
- [ ] Set up SSL certificate on VPS (Let's Encrypt)

### Backend
- [x] Create `backend/` directory with FastAPI structure
- [x] SQLAlchemy models en `backend/models.py` (PostgreSQL v2)
- [x] Routers en `backend/routers/` (auth, users, persons, search, source_files, analysis)
- [x] Alembic migrations (`backend/alembic/versions/20260612_194138_v2_shared_assets.py`)
- [x] Migración v1→v2 vía `backend/migrate_data.py`
- [x] Ingesta UPSERT vía `backend/rnp_ingest_pg.py`
- [ ] Deploy to VPS via Docker or systemd
- [ ] Configure Nginx reverse proxy with SSL
- [ ] Verify CORS works with Vercel domain

### Frontend
- [ ] Create `vercel.json` with rewrites
- [ ] Test locally with rewrites pointing to VPS
- [ ] Deploy to Vercel
- [ ] Verify login flow works end-to-end
- [ ] Verify analysis job polling works

### Post-deployment
- [ ] Monitor VPS logs for errors
- [ ] Set up automated backups for PostgreSQL
- [ ] Add health check endpoint (`GET /api/health`)
- [ ] Consider rate limiting on API endpoints

---

## Estimated Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| 1. Security | 1 hour | **Critical - do now** |
| 2. Database migration | 2-3 hours | High |
| 3. Backend rewrite | 6-8 hours | High |
| 4. Frontend deploy | 30 minutes | Medium |
| 5. Scraping scripts update | 2-3 hours | Medium |
| 6. Testing & polish | 2-3 hours | High |

**Total: ~14-18 hours**
