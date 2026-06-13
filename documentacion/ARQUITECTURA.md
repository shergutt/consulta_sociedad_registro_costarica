# Arquitectura del Sistema

## Visión general

**RNP Intelligence Desk** es un sistema de inteligencia registral que automatiza la extracción, persistencia, análisis y visualización de datos del Registro Nacional de Costa Rica.

El sistema se divide en 3 capas principales:

```
┌─────────────────────────────────────────────────────────────┐
│                      DASHBOARD (Vercel)                     │
│              HTML/CSS/JS Vanilla SPA                        │
│              proxy /api/* → VPS                             │
└─────────────────────────┬───────────────────────────────────┘
                          │ API REST
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (VPS - Docker)                    │
│  FastAPI + SQLAlchemy + PostgreSQL                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Routers  │  │ Services │  │  Models  │                  │
│  │ (6 mods) │  │ (Jobs)   │  │ (12 tbl) │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ subprocess + mmx-cli
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SCRAPERS + ANÁLISIS (Python)                    │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ Scrapers │→│ build_rnp_   │→│ PostgreSQL        │      │
│  │ (27 py)  │  │ report.py    │  │ (persistencia)   │      │
│  └──────────┘  └──────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Decisiones de diseño clave

### 1. Scrapers con solo standard library
- No dependen de requests, BeautifulSoup ni Selenium
- Manejan manualmente: JSF ViewState, A4J tokens, cookies de sesión
- El RNP solo permite 1 sesión activa por usuario — los scrapers cierran sesiones existentes automáticamente

### 2. Base de datos compartida (PostgreSQL)
- Migración de SQLite (por usuario) a PostgreSQL compartido
- Tabla `person_queries` como junction para control de acceso: un usuario ve solo personas que ha consultado
- Admins ven todo

### 3. Jobs en memoria con threads
- Los análisis pesados corren en `threading.Thread` daemon
- Estado en diccionario en memoria (`_jobs` con lock)
- No hay persistencia de jobs — si el servidor se reinicia, se pierden

### 4. MiniMax como gatekeeper
- Antes de ejecutar un análisis, se consulta a MiniMax M3 vía `mmx-cli`
- MiniMax valida la cédula y autoriza (o no) la ejecución del skill local
- Esto añade una capa de seguridad y validación semántica

### 5. Frontend vanilla sin framework
- SPA con JavaScript vanilla (sin React, Vue, etc.)
- Paleta de comandos (`Ctrl+K`) para búsqueda global
- Temas claro/oscuro con design tokens en CSS
- Diálogos nativos `<dialog>`

## Flujo de datos completo

```
1. Usuario ingresa cédula en el Dashboard
       ↓
2. POST /api/run-analysis
       ↓
3. Backend valida cédula (9-12 dígitos)
       ↓
4. MiniMax preflight: autoriza la operación
       ↓
5. Thread ejecuta build_rnp_report.py:
   a. Login al RNP con credenciales de .env
   b. Extrae: datos persona, fincas, bienes muebles,
      vehículos, aeronaves, buques, catastro,
      gravámenes, historiales, diario, anotaciones
   c. Ejecuta análisis con MiniMax
   d. Persiste todo en PostgreSQL
       ↓
6. Dashboard obtiene /api/jobs/{id} (polling)
       ↓
7. Dashboard carga /api/persons/{cedula}/detail
       ↓
8. Usuario navega fincas, bienes muebles, alertas, fuentes
```

## Modelo de seguridad

- **Autenticación**: HTTP Bearer token con `pbkdf2_hmac` (SHA-256, 100k iteraciones)
- **Sesiones**: expiran en 24h, almacenadas en tabla `sessions`
- **Roles**: `admin` y `user`
- **Control de acceso a datos**: vía `person_queries` — solo el usuario que consultó una persona puede ver sus datos (excepto admin)
- **Credenciales RNP**: en `.env`, pasadas vía variables de entorno al subprocess
