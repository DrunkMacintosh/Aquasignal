# AquaSignal Dashboard

React dashboard for the AquaSignal groundwater risk API. Built for water
authority staff: open the map, see which areas are at risk, click in, read the
6-month trend, export a report.

The map has two views (toggle top-left, choice remembered): **Districts** —
all 63 provinces/cities of Vietnam coloured by area-weighted risk (default),
and **Grid detail** — the model's native 0.25° cells, clipped to the
coastline and national border. Both share one map engine; switching flips
layer visibility only. Clicking either opens a panel with the risk score,
6-month forecast, history, **raw satellite observations** (GRACE underground
water storage, Sentinel-1 ground radar signal — a subsidence *proxy*, not a
measured rate — plus ERA5-Land rainfall, evaporation demand, and air
temperature), reports, and alerts.

## Stack

React 18 · Vite · Tailwind CSS · MapLibre GL · Recharts · Axios ·
TanStack React Query v5 · Vitest

## Setup

```bash
cd frontend
npm install
npm run dev                  # http://localhost:3000 — no map token needed
```

The dev server is pinned to port **3000** because the backend's default CORS
allowlist (`AQUASIGNAL_CORS_ORIGINS`) only contains `http://localhost:3000`.
Start the backend with `uvicorn app:app --reload --port 8000` from `backend/`.

One-time data setup (boundaries from
[geoBoundaries](https://www.geoboundaries.org) VNM ADM1, Public Domain):

```bash
cd backend
python -m alembic upgrade head
python scripts/seed_districts.py ../data/boundaries/geoBoundaries-VNM-ADM1_simplified.geojson --all
python scripts/clip_cells_to_land.py   # clips grid cells to coast/border
```

Accounts can be created from the sign-in screen ("Create an account"), backed
by `POST /auth/register`. Self-registration always yields the lowest-privilege
`field_officer` role; admins are promoted via `backend/scripts/create_user.py`.
Emails are normalized to lowercase server-side, passwords need 12+ characters.

| Env var          | Purpose                                   | Default                 |
| ---------------- | ----------------------------------------- | ----------------------- |
| `VITE_API_URL`   | FastAPI base URL                          | `http://127.0.0.1:8000` |

> Vite only exposes `VITE_`-prefixed variables to the browser, so the CRA-style
> `REACT_APP_*` names do not apply here.

The map runs on **MapLibre GL** over a keyless satellite basemap — Esri World
Imagery with Esri's boundaries-and-places label overlay (attribution shown on
the map, as Esri's terms require). No map account or token is needed. To use Mapbox tiles
instead, set `VITE_MAP_STYLE` to a Mapbox style URL including your
`?access_token=pk.*` query parameter — the rest of the map code is unchanged.

`npm run test` runs the unit tests; `npm run build` produces `dist/`.

## Design decisions

### Why the JWT is never put in localStorage

- `localStorage` is synchronously readable by **any** JavaScript running on the
  origin. One XSS hole (a compromised dependency, an injected script) and the
  attacker walks away with a 24-hour bearer token they can replay from anywhere.
- These are government workstations, often shared: localStorage persists after
  the browser closes, so the next person at the desk would inherit a live session.
- Instead the token lives in module memory (`src/api/client.js`) set by
  `AuthContext`. A page refresh costs a re-login — an acceptable trade for staff
  who keep one tab open all day. The stronger long-term fix is an `httpOnly`
  cookie session, which requires backend changes.

### Map updates without re-initialising the map engine

`src/components/Map.jsx` creates the map exactly once. The choropleth is a
GeoJSON source + `fill` layer whose colour is a `step` expression on
`current_risk`. When React Query delivers fresh data, the component calls
`map.getSource('risk-cells').setData(geojson)` — MapLibre re-renders the layer on
the GPU while camera position, event handlers, and hover state (via
`promoteId: 'cell_id'` + feature-state) all survive untouched.

### Stale-while-revalidate

React Query keeps the last successful response in cache (`gcTime: 24h`).
Renders always serve from cache instantly; when data is older than `staleTime`
(5 min for the map) a background refetch runs. If the API is down the refetch
fails but the cached data **stays** — `isError && data` triggers the amber
"Data unavailable — showing last cached data" banner instead of a blank screen.

## Known backend gaps the UI works around

| Gap | Workaround |
| --- | --- |
| ~~No `POST /auth/refresh`~~ **Resolved** | Sessions renew silently 5 min before expiry; the expiry warning only appears if the renew call fails (offline/server down). |
| ~~No `GET /districts`~~ **Resolved** | `GET /risk-map/districts` powers the district view and the panel's picker; the static list in `src/lib/districts.js` remains only as an offline fallback. |
| ~~No JSON history endpoint~~ **Resolved** | Sparklines use `GET /history/{cell_id}` and `GET /history/district/{name}`. |
| ~~Per-district unsubscribe missing~~ **Resolved** | `DELETE /alerts/subscribe/{token}/{district}` — the delete-all-and-resubscribe dance is gone. |
| No cell→district lookup | The cell panel has a remembered district picker for reports/alerts. |
| No "list my subscriptions" | Subscriptions mirrored in localStorage (`src/lib/subscriptions.js`) to drive the critical-alert banner. |
| Subscribe expects an FCM token | A stable per-browser `web-<uuid>` identifier is sent instead (`src/lib/deviceToken.js`). |
