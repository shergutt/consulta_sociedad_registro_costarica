# Dashboard (Frontend SPA)

Single Page Application vanilla HTML/CSS/JS desplegada en Vercel. Sin frameworks ni librerías externas (solo Google Fonts).

## Estructura

```
dashboard/
├── index.html               # Shell de la SPA
├── vercel.json              # Config Vercel (rewrites API)
├── css/
│   ├── tokens.css           # Design tokens (colores, typografía, spacing)
│   ├── base.css             # Reset y estilos base
│   ├── components.css       # Componentes reutilizables
│   ├── layout.css           # Layout del app-shell
│   └── responsive.css       # Media queries responsivos
└── js/
    ├── app.js               # Controlador principal SPA
    ├── api.js               # Helpers fetch/post/delete con auth
    ├── state.js             # Estado global + localStorage
    ├── utils.js             # Utilidades generales
    ├── theme.js             # Toggle tema claro/oscuro
    ├── ui.js                # Renderizado de UI
    ├── search.js            # Paleta de búsqueda global (⌘K)
    ├── admin.js             # Diálogo de administración de usuarios
    └── jobs.js              # Monitoreo de jobs con polling
```

## Componentes del HTML (`index.html`)

### Pantalla de Login
- Formulario usuario/contraseña
- Manejo de errores (credenciales inválidas)
- Token guardado en `localStorage`

### App Shell
- **App bar**: logo, búsqueda (⌘K), acciones (nuevo análisis, refresh, jobs chip, theme toggle, menú usuario)
- **Side panel**: lista de personas consultadas, filtro por cédula
- **Main content**: hero + métricas + detalle de persona con tabs
- **Backdrop**: para side panel en móvil

### Diálogos (`<dialog>`)
1. **Nuevo Análisis**: formulario para ingresar cédula
2. **Job Drawer**: monitoreo en vivo del job (status + log)
3. **Admin Dialog**: CRUD de usuarios (solo admin)
4. **Source Dialog**: contenido crudo de archivos fuente
5. **Report Dialog**: reporte de análisis (Markdown)
6. **Confirm Dialog**: confirmación para acciones destructivas

### Tabs de detalle de persona
1. **Resumen**: vista general con métricas
2. **Fincas**: lista de propiedades con detalles
3. **Bienes Muebles**: vehículos y otros activos
4. **Evidencia**: queries ejecutadas con sus respuestas crudas
5. **Fuentes**: archivos fuente (JSON/HTML/TXT)

## Módulos JavaScript

### `app.js` — Controlador principal
- Routing: manejo de vistas (login, persons list, person detail)
- Event handlers globales
- Ciclo de vida de la SPA
- Lógica de tabs y navegación

### `api.js` — Capa de comunicación
- `apiGet(url)`, `apiPost(url, body)`, `apiDelete(url)`
- Incluye header `Authorization: Bearer {token}` automáticamente
- Manejo de errores HTTP (401 → redirect a login)

### `state.js` — Estado global
- `state.currentUser`, `state.persons`, `state.selectedPerson`, `state.jobs`
- Persistencia de token en `localStorage`
- Funciones `setToken()`, `getToken()`, `clearToken()`

### `ui.js` — Renderizado
- `renderPersonList()`, `renderSummary()`, `renderFincas()`, `renderMovableAssets()`
- `renderMetrics()`, `renderAlerts()`
- Construcción de HTML desde datos

### `search.js` — Búsqueda global
- Activación con `Ctrl+K` o click
- Búsqueda en API `/api/search?q=...`
- Resultados agrupados por tipo (personas, fincas, bienes muebles)
- Navegación con teclado (↑↓Enter)

### `jobs.js` — Monitoreo de jobs
- Polling a `/api/jobs/{id}` cada 2 segundos
- Actualización de estado en vivo
- Log tail en el drawer

### `theme.js` — Temas
- Toggle claro/oscuro
- Persistencia en `localStorage`
- Design tokens via CSS custom properties

### `admin.js` — Admin panel
- Listar usuarios
- Crear usuario (username + password + role)
- Eliminar usuario (con confirmación)

## Diseño y CSS

### Sistema de diseño
- **Design tokens**: `tokens.css` define colores, tipografía, spacing, bordes, sombras
- **Tema claro/oscuro**: variables CSS cambian según clase `.dark` en `<body>`
- **Tipografía**: IBM Plex Sans (texto) + IBM Plex Mono (código/data)

### Layout
- App shell con sidebar colapsable
- Grid responsivo para métricas
- Cards para fincas y bienes muebles
- Drawer para jobs (slide desde la derecha)

### Responsive
- Sidebar se oculta en móvil, toggle con botón hamburguesa
- Grids se apilan en pantallas pequeñas
- Tablas se vuelven scroll horizontal
- Diálogos full-screen en móvil

## Vercel deployment

- `vercel.json` principal en la raíz del proyecto
- Rewrite `/api/*` → `https://api.example.com/api/*`
- Security headers (CORS, XSS, etc.)
- Proyecto Vercel: `prj_Lfg2KuNQXZ17QNCRNEneYYaCUMIA`
