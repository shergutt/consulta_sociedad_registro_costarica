# RNP Intelligence Desk — Documentación

Sistema full-stack para consultar, persistir y analizar registros públicos del **Registro Nacional de Costa Rica (RNP)** desde `rnpdigital.com`.

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| **Scrapers** | Python 3 (solo standard library) |
| **Backend API** | FastAPI + SQLAlchemy + PostgreSQL |
| **Frontend** | HTML/CSS/JS vanilla (SPA) |
| **Despliegue** | Docker (backend), Vercel (frontend) |
| **IA** | MiniMax M3 vía `mmx-cli` |

## Estructura del proyecto

```
├── documentacion/               ← Esta documentación
├── backend/                     ← API REST (FastAPI + PostgreSQL)
├── dashboard/                   ← SPA frontend (Vercel)
├── *.py                         ← Scrapers (raíz del proyecto)
├── datos/analisis/              ← Resultados de análisis de 5 personas
├── .env                         ← Credenciales (RNP, MiniMax)
├── Dockerfile                   ← Contenedor del backend
├── vercel.json                  ← Config de deploy en Vercel
└── DEPLOYMENT_PLAN.md           ← Plan de despliegue arquitectónico
```

## Índice de documentos

| Documento | Contenido |
|-----------|-----------|
| [ARQUITECTURA.md](ARQUITECTURA.md) | Visión general de la arquitectura, flujo de datos y decisiones de diseño |
| [SCRAPERS.md](SCRAPERS.md) | Documentación de los 27 scrapers Python |
| [BACKEND.md](BACKEND.md) | API REST, autenticación, jobs y servicios |
| [DASHBOARD.md](DASHBOARD.md) | Frontend SPA, componentes y lógica del lado del cliente |
| [BASE_DE_DATOS.md](BASE_DE_DATOS.md) | Esquema PostgreSQL, tablas, índices y relaciones |
| [DATOS_ANALISIS.md](DATOS_ANALISIS.md) | Resultados de análisis para las 5 personas |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Configuración, despliegue y variables de entorno |

## Flujo de alto nivel

```
rnpdigital.com (Registro Nacional)
       ↓
  [Scrapers Python]  ←──  extraen datos crudos (JSON/HTML/TXT)
       ↓
  [Análisis]  ←──  build_rnp_report.py + MiniMax IA
       ↓
  [PostgreSQL]  ←──  persistencia centralizada
       ↓
  [FastAPI]  ←──  API REST
       ↓
  [Dashboard]  ←──  SPA en Vercel (proxy → VPS)
```
