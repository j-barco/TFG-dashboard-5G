# Frontend del panel de monitorización y gestión — TFG Juan Barco Gil

React + Vite + Tailwind CSS v4, consumiendo el backend FastAPI del mismo
proyecto (`dashboard-backend/`).

## Identidad visual

El diseño se aparta deliberadamente de la plantilla genérica de "panel
SaaS" (fondo negro puro + verde neón, o crema + terracota): fondo azul-
pizarra profundo, indicador de estado en forma de barras de analizador de
espectro (`SignalPulse`) en vez del habitual punto de semáforo, y una
pareja tipográfica IBM Plex Sans/Mono + Space Grotesk, coherente con la
naturaleza de instrumentación de radio del propio proyecto.

## Instalación

```bash
npm install
```

## Configuración

```bash
cp .env.example .env
```
Por defecto asume que el backend corre en `http://localhost:8000`
(mismo equipo). Ajusta `VITE_API_BASE_URL` si no es el caso.

## Arrancar en desarrollo

```bash
npm run dev
```
Por defecto en `http://localhost:5173`.

## Compilar para producción

```bash
npm run build
```
Genera `dist/`, servible como ficheros estáticos por cualquier servidor
web (incluido el propio backend FastAPI, montando `StaticFiles` sobre
`dist/`, si se prefiere un único proceso en vez de dos).

## Estructura

```
src/
├── api/
│   ├── client.js       # Instancia de axios: token automático, logout en 401
│   └── endpoints.js    # Una función por endpoint del backend
├── context/
│   └── AuthContext.jsx # Estado de sesión (token, si la auth está activada)
├── hooks/
│   └── usePolling.js   # Sondeo periódico con degradación controlada
├── components/
│   ├── Layout.jsx       # Barra lateral + estructura de página
│   ├── SignalPulse.jsx  # Indicador de estado (elemento distintivo)
│   ├── Card.jsx          # Contenedor y cabecera de página reutilizables
│   └── ProtectedRoute.jsx
└── pages/
    ├── Login.jsx
    ├── Overview.jsx       # Resumen: core + gNB + UEs conectados
    ├── GnbConfig.jsx       # Configuración y reinicio del gNB
    ├── CoreServices.jsx    # Arranque/parada de cada NF
    └── Subscribers.jsx     # Alta/baja de suscriptores
```

## Notas de diseño relevantes para la memoria

- **Degradación controlada**: si una consulta de sondeo falla, la interfaz
  mantiene el último dato válido en pantalla en vez de vaciarse, siguiendo
  el mismo criterio ya aplicado en el propio backend (ver Metodología).
- **Distinción `monitored`/`reachable`**: el listado de funciones de red
  refleja explícitamente las NFs sin soporte de métricas como "no
  monitorizable", nunca como "caída" (ver Implementación y Desarrollo,
  incidencia de métricas de Open5GS).
- **Sesión**: el token se guarda en `localStorage` (aplicación de
  escritorio de uso local, no un widget embebido de terceros) y se limpia
  automáticamente ante cualquier respuesta 401 del backend.
