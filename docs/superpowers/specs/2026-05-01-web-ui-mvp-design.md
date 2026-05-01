# Web UI MVP — Design Spec

**Date:** 2026-05-01
**Status:** Approved

---

## Goal

Build a React 18 + Vite frontend for TestWeaveX that serves 3 screens (Dashboard, Test Cases, Gap Report), wired to the existing live API endpoints, and visually identical to the existing `static/index.html` design.

## Architecture

- **Source:** `frontend/` at repo root (Vite + React 18 project)
- **Build output:** `testweavex/web/static/` — replaces the existing vanilla JS `index.html`
- **Backend:** No changes needed. FastAPI's existing `StaticFiles` mount at `/` already serves from `testweavex/web/static/`
- **Routing:** `useState`-based navigation in `App.jsx` — no React Router for MVP

## Tech Stack

- React 18
- Vite 5
- Plain CSS (copied from existing `index.html` `<style>` block)
- No CSS framework, no state management library, no routing library

---

## File Structure

```
frontend/
├── index.html
├── vite.config.js          ← build.outDir: ../testweavex/web/static
├── package.json
└── src/
    ├── main.jsx
    ├── App.jsx             ← sidebar + useState({ view: 'dashboard' })
    ├── styles.css          ← CSS copied from existing index.html
    ├── api.js              ← one fetch function per endpoint
    └── components/
        ├── Sidebar.jsx
        ├── Dashboard.jsx
        ├── TestCases.jsx
        └── GapReport.jsx
```

---

## Components

### App.jsx

Top-level component. Renders `<Sidebar>` and the active screen based on a `view` state string. Passes `setView` down to `Sidebar`.

```jsx
const [view, setView] = useState('dashboard')
```

Renders one of: `<Dashboard />`, `<TestCases />`, `<GapReport />`.

### Sidebar.jsx

Static nav with 3 links: Dashboard, Test Cases, Gap Report. Applies an `active` CSS class to the current view. Calls `setView(name)` on click. Matches existing dark sidebar (`#1A1A2E`, existing `.sidebar` CSS class).

### Dashboard.jsx

Fetches `GET /api/dashboard` on mount. Displays:
- 4 KPI cards (reuse `.kpi-card` CSS):
  - **Total Tests** ← `total_test_cases`
  - **Automated %** ← `coverage_percentage` (formatted as `75.0%`)
  - **Open Gaps** ← `open_gaps`
  - **Last Run** ← `last_run_id` truncated to 8 chars, or "None" if null
- Coverage sparkline using existing `.sparkline` CSS

Loading state: skeleton placeholders. Error state: inline error message.

### TestCases.jsx

Fetches `GET /api/test-cases` on mount. Displays a table with columns:
- Title, Type (badge), Automated (yes/no badge), Priority, Status (badge)

Two dropdowns above the table:
- Filter by `test_type`
- Filter by `is_automated` (All / Automated / Manual)

Filtering is client-side (filter the fetched array in state).

### GapReport.jsx

Fetches `GET /api/gaps?limit=20` on mount. Displays a ranked table:
- Score, Reason, Test Case ID

Each row has a **Generate** button. On click:
- Button shows a spinner and is disabled
- Calls `POST /api/gaps/{gap_id}/generate`
- On success: renders each `scenario.gherkin` from `response.scenarios[]` as a collapsible block below the row (one block per scenario)
- On error: shows an inline error message on the row

---

## Data Flow

Each screen is self-contained — fetches its own data, owns its loading/error state. No global state, no context, no caching.

Pattern per screen:

```jsx
const [data, setData] = useState(null)
const [loading, setLoading] = useState(true)
const [error, setError] = useState(null)

useEffect(() => {
  getFoo()
    .then(setData)
    .catch(e => setError(e.message))
    .finally(() => setLoading(false))
}, [])
```

---

## API Module (`api.js`)

```js
const BASE = ''  // same-origin in prod; proxied in dev

export const getDashboard = () =>
  fetch(`${BASE}/api/dashboard`).then(r => r.json())

export const getTestCases = () =>
  fetch(`${BASE}/api/test-cases`).then(r => r.json())

export const getGaps = (limit = 20) =>
  fetch(`${BASE}/api/gaps?limit=${limit}`).then(r => r.json())

export const generateForGap = (gapId) =>
  fetch(`${BASE}/api/gaps/${gapId}/generate`, { method: 'POST' }).then(r => r.json())
```

---

## Vite Config

```js
// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../testweavex/web/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
    },
  },
})
```

---

## CSS Strategy

Copy the entire `<style>` block from `testweavex/web/static/index.html` into `src/styles.css`. Import it in `main.jsx`. Apply existing class names (`.sidebar`, `.kpi-card`, `.badge`, `.sparkline`, `.table`, etc.) in JSX components. No new CSS invented.

---

## Build & Dev Workflow

```bash
# Development (hot reload, proxies API to FastAPI on :8080)
cd frontend
npm install
npm run dev        # Vite dev server on :5173

# Production build (writes to testweavex/web/static/)
npm run build

# Then serve:
tw serve           # FastAPI serves the built React app at http://localhost:8080
```

---

## Out of Scope (MVP)

- Generation Review screen
- Live Run screen
- Run History screen
- Settings screen
- SSE live streaming (`/api/events`)
- React Router / URL-based navigation
- Authentication
- Dark/light mode toggle
