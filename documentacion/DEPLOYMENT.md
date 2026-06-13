# Despliegue y Configuración

## Arquitectura de despliegue

```
rnpdigital.com (RNP, fuente de datos)
       ↑
[VPS] HOST
├── Backend Docker (puerto 8000)
│   ├── FastAPI + SQLAlchemy
│   ├── Python 3.12 + mmx-cli
│   └── Credenciales RNP + MiniMax
└── PostgreSQL (puerto 8081)
    └── rnp_intelligence DB

[Vercel]
└── Dashboard SPA
    └── Proxy /api/* → https://api.example.com/api/*
```

## Backend Docker

### Dockerfile
```dockerfile
FROM python:3.12-slim
# Instala gcc, nodejs, npm
# Copia backend/
# pip install -r requirements.txt
# npm install -g mmx-cli
# EXPOSE 8000
# CMD uvicorn main:app --host 0.0.0.0 --port 8000
```

### Build y run
```bash
docker build -t rnp-backend .
docker run -d \
  --name rnp-backend \
  -p 8000:8000 \
  --env-file .env \
  rnp-backend
```

## Variables de entorno (`.env`)

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | `postgresql://user:pass@host:port/db` |
| `RNP_USER` | Usuario del portal rnpdigital.com |
| `RNP_PASS` | Contraseña del portal rnpdigital.com |
| `MINIMAX_API_KEY` | API key de MiniMax AI |
| `CORS_ORIGINS` | Orígenes CORS separados por coma |
| `SESSION_HOURS` | Duración de sesión en horas (default: 24) |
| `REQUIRE_MINIMAX` | Si se requiere autorización MiniMax (default: true) |

**⚠️ IMPORTANTE**: Las credenciales de `.env` están trackeadas en git history. Rotar inmediatamente y purgar con `git-filter-repo`.

## Frontend Vercel

### vercel.json (raíz del proyecto)
```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://api.example.com/api/$1" }
  ],
  "headers": [
    { "source": "/(.*)", "headers": [
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "X-Frame-Options", "value": "DENY" },
      { "key": "X-XSS-Protection", "value": "1; mode=block" }
    ]}
  ]
}
```

### Deploy
```bash
vercel --prod
```

## Base de datos PostgreSQL

### Migraciones (Alembic)
```bash
cd backend/
alembic upgrade head
```

La migración actual (`20260612_194138_v2_shared_assets.py`) crea las 12 tablas del esquema v2.

## Pendientes

- [ ] Verificar migraciones en producción
- [ ] Desplegar Docker en VPS
- [ ] Desplegar Dashboard en Vercel
- [ ] Rotar credenciales expuestas en git
- [ ] Verificar proxy API desde Vercel → VPS
- [ ] Configurar healthcheck endpoint `/api/health`
