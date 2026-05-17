# CLAUDE.md — websites monorepo

This file provides guidance to Claude Code when working in the `~/DockerApps/websites/` directory.

**Also read the parent `~/DockerApps/CLAUDE.md`** — its safety rules (don't change paths, ports, volumes, networks) always apply.

---

## Architecture Overview

This is an **npm workspace monorepo** containing 4 Vue 3 apps and a shared component library. All Vue apps are built via Docker (`node:22-alpine`) since Node/npm is NOT installed on the tower.

```
websites/
├── package.json              # Workspace root (shared deps: vue, vite, tailwind, postcss)
├── tailwind.config.js        # Shared Tailwind theme (dark color palette)
├── postcss.config.js         # Shared PostCSS config
├── deploy.sh                 # Unified build script
├── packages/
│   └── shared/               # @webhead/shared — shared components, composables, styles
│       ├── package.json
│       ├── index.js           # Barrel export
│       ├── styles.css         # Scrollbar-hide, thin-scrollbar, sortable-ghost (CSS var for color)
│       ├── composables/
│       │   └── useApi.js      # Parameterized API fetch wrapper (storageKey, headerName)
│       └── components/
│           ├── Toast.vue      # Auto-dismiss toast notification
│           ├── AuthGate.vue   # Key-based auth gate (props-driven)
│           ├── SearchBar.vue  # Debounced search input with v-model
│           ├── PosterCard.vue # Movie/show poster card with overlays
│           └── LoadingDots.vue # Bouncing dots loading indicator
├── status-hub/               # akplex.tv/status/ — main dashboard
├── collection-manager/       # akplex.tv/collections/ — admin Plex collection CRUD
├── movies-feed/              # akplex.tv/recently-added/ — recently added feed
├── kelly-collection/         # akplex.tv/kelly/ — Kelly's personal collection editor
├── hub-site/                 # Static HTML: /request, /issues, /join pages
├── announce/                 # Static HTML: /announce — admin form, POSTs /api/announcement
├── docker-services/          # Static HTML: /services page
├── request-form/             # Static HTML: content request form
├── issue-report/             # Static HTML: issue report form
├── join-request/             # Static HTML: join request form
├── request-form-gcp/         # GCP copy of request form (unused on tower)
└── node-backend/             # GCP Express.js backend (unused on tower)
```

---

## Key Rules

1. **Node/npm is NOT installed on the tower.** All builds run via Docker:
   ```bash
   docker run --rm -v "$(pwd):/app" -w /app node:22-alpine sh -c "npm install --silent && npm run build -w <app>"
   ```

2. **`dist/` folders are live immediately.** Web-router volume-mounts them read-only. Any rebuild updates the live site — no container restart needed.

3. **Don't change `vite.config.js` base paths** without also updating `router/consolidated.conf` and the web-router volume mounts in `docker-compose.yaml`.

4. **Don't change API proxy targets** — they match the container names and ports in docker-compose.yaml:
   - `/api` -> `announcement-api:5000` (container port 5050)
   - `/capi` -> `collection-api:5000` (container port 5060)

5. **The `@webhead/shared` package is a workspace dependency** — import from it with `import { Toast, useApi } from '@webhead/shared'`.

---

## Build & Deploy

```bash
cd ~/DockerApps/websites

# Build all 4 Vue apps
./deploy.sh

# Build specific app(s)
./deploy.sh status-hub
./deploy.sh collection-manager kelly-collection

# Manual single-workspace build
docker run --rm -v "$(pwd):/app" -w /app node:22-alpine sh -c "npm install --silent && npm run build -w movies-feed"
```

Old per-app `deploy.sh` scripts still exist in each app directory but are superseded by the root one.

---

## Shared Package: @webhead/shared

### useApi composable

Parameterized API fetch wrapper. Each app wraps it with its own config:

```js
// In app's src/composables/useApi.js
import { useApi as useSharedApi } from '@webhead/shared'

const api = useSharedApi({
  storageKey: 'collection_manager_admin_key',  // localStorage key
  headerName: 'X-Admin-Key'                    // HTTP header for auth
})

export function useApi() {
  return {
    adminKey: api.authKey,        // aliased to preserve existing variable names
    setAdminKey: api.setAuthKey,
    clearAdminKey: api.clearAuthKey,
    apiFetch: api.apiFetch
  }
}
```

**Current app configs:**
| App | storageKey | headerName |
|-----|-----------|------------|
| collection-manager | `collection_manager_admin_key` | `X-Admin-Key` |
| kelly-collection | `kelly_collection_key` | `X-Kelly-Key` |

### Shared styles (styles.css)

Imported in each app's `style.css` with `@import '@webhead/shared/styles.css';` (must be first line, before `@tailwind` directives).

Provides: `.scrollbar-hide`, `.thin-scrollbar`, `.sortable-ghost` / `.sortable-chosen` / `.sortable-drag`.

The sortable-ghost border color uses CSS variable `--sortable-color` (default: purple). Kelly-collection overrides it:
```css
:root { --sortable-color: rgba(244, 114, 182, 0.5); }
```

### Components

Available but not yet imported in all apps. Can be used via:
```js
import { Toast, AuthGate, SearchBar, PosterCard, LoadingDots } from '@webhead/shared'
```

collection-manager still uses its own local component files (AuthGate, Toast, SearchBar, PosterCard) which are near-identical to the shared versions. These can be migrated to shared imports in a future cleanup.

---

## Per-App Details

### status-hub (akplex.tv/status/)
- **Base path:** `/status/`
- **API proxy:** `/api` -> `http://host.docker.internal:5050`
- **Backend:** announcement-api (Flask, built from `websites/status-hub/Dockerfile`)
- **No auth required** — public dashboard
- **Components:** `App.vue` (main), `MovieGrid.vue`, `NavCard.vue` (legacy, may be unused)

#### Layout Structure (App.vue)
```
Header:    [Logo + Title]  [Search bar]  [CPU% | GPU°]  [● N Active]
App Cells: [AK's Plex ›]  [Request ›]  [Report Bugs ›]   ← 3-col grid (1-col mobile)
Status:    [● Plex OK]  [● Supporting Sites OK]           ← stacked bars
Bookmarks: [New Uploads]  [Anonymous Message]              ← 2-col compact grid
Calendar:  TV Calendar (horizontal scroll, 4 days)
Trending:  Trending Movies (horizontal scroll, MovieGrid)
Tips:      Plex Tips & Tricks (coming soon placeholder)
Footer:    WebHead Media © 2025 + Report an Issue link
```

#### App Cells (top row)
3 large horizontal cards — icon left, label, chevron right. On mobile (< `sm`), they stack into a single column.
- **AK's Plex** — links to `app.plex.tv/desktop`, has Plex status dot (green/red, top-right corner)
- **Request** — links to `akplex.tv/request`, blue border/glow accent, has Seerr status dot
- **Report Bugs** — links to `akplex.tv/issues`, red hover glow

#### Status Bars
Two stacked full-width bars showing live service health:
- **Plex** — green dot + `OK` badge when `stats.plexOnline === true`
- **Supporting Sites** — reflects `overseerrStatus.status` (online/degraded/offline)

#### Bookmarklets
Compact 2-col grid. Smaller than app cells, similar styling to status bars:
- **New Uploads** — `<a>` to `/recently-added`, library icon (Lucide)
- **Anonymous Message** — `<button>` that opens the message modal (`msgOpen`)

#### Header Stats
- **CPU/GPU** — stacked vertically, `hidden sm:flex`. CPU shows percentage, GPU shows temperature with color coding (green < 65°, amber 65-80°, red > 80°). Tooltip on hover.
- **Active streams** — always visible pill with pulsing green dot when `stats.streams > 0`

#### Search Bar
- Always visible in header, `max-w-xs sm:max-w-sm`
- `/` keyboard shortcut to focus
- Debounced Plex library search via `/api/search?q=...` (searches Plex directly)
- Results dropdown shows thumbnail, title, year, type
- Each result has a flag icon for one-click issue reporting (`reportIssue()` → POST `/api/issue-report`)
- Clicking a result opens in Plex web (`pickResult()`)

#### TV Calendar
- 4 days: Yesterday → day-after-tomorrow
- Horizontal scroll on mobile, flex row on desktop
- Episodes show download status dots (green = uploaded, amber = missing, gray = not aired)
- Expandable via "+N more" / Collapse button (max-h-[250px] with overflow-y-auto)
- Data from `/api/sonarr-calendar` (Sonarr API)

#### MovieGrid Component
- Fetches from `/api/trending-movies` (MDB List `linaspurinis/trending-movies-list`, 100 items × Radarr library cross-reference). The earlier `most-popular-movies-top-20` source went stale (shrunk to 6 items) — switched May 10 2026.
- `layout` prop: `"horizontal"` (scrollable row) or `"grid"` (responsive CSS grid)
- `limit` prop controls how many movies to show (default 10, status-hub uses 7)
- Movies with Plex matches get deep-link URLs; others render as non-clickable `<div>`
- Poster size: `min-w-[130px] max-w-[180px]` in horizontal mode
- 10-minute auto-refresh interval

#### Anonymous Message Modal
- Teleported to `<body>` for z-index isolation
- Fade transition (uses unscoped `<style>` — Vue scoped styles don't apply to teleported content)
- POST to `/api/anon-request` with message text
- Shows "Sent!" confirmation, auto-clears after 2s

#### Announcement Banner
- Fetched from `/api/announcement` on mount + 60s interval
- Severity colors: red/yellow/green/resolved/info
- Dismissible (per-session, not persisted)
- Shows above header when `announcement.enabled && !announcement.dismissed`

#### Welcome Message
- One-time "Welcome to AK's Plex" banner for first-time visitors
- Stored in `localStorage` as `akplex_welcome_seen`
- Auto-dismisses after 4 seconds

### collection-manager (akplex.tv/collections/)
- **Base path:** `/collections/`
- **API proxy:** `/capi` -> `http://localhost:5060`
- **Backend:** collection-api (Flask + plexapi)
- **Auth:** X-Admin-Key header (key: `webhead-admin-2026`)
- **Extra dep:** `vue-draggable-plus` (drag-and-drop collection ordering)

### movies-feed (akplex.tv/recently-added/)
- **Base path:** `/recently-added/`
- **Lazy load:** each tab (Movies / Episodes / Requests) starts at 20 items and bumps by 20 when an IntersectionObserver sentinel near the bottom enters view. Switching tabs resets all caps and scrolls to top.
- **API proxy:** `/api` -> `http://localhost:5050`
- **Backend:** announcement-api (Flask)
- **No auth required** — public feed
- **Single file app** — everything in `App.vue`

#### Layout
- Header with garfield logo, "Recently Added" title, back-link to `/status/` (Hub)
- Tabs: Movies / Episodes
- Pull-to-refresh on mobile, refresh button (top-right) on desktop
- Auto-refreshes every 60 seconds

#### Movies Tab
- Grouped by time period: Today / Yesterday / This Week / Last Week / Earlier
- Each group in a subtle `bg-white/[0.02] border border-white/5 rounded-2xl` section wrapper
- Section headers show group name + item count: `"Today (3)"`
- Grid: `grid-cols-3 sm:4 md:5 lg:7`
- Cards: poster + title + year below, fuchsia time-ago label
- Data from `/api/recently-added-movies`

#### Episodes Tab
- Grouped by series (multiple episodes of same show collapsed)
- Badge shows episode count when > 1
- Episode label: `S1E3` or `S1E3-E5` or `"N episodes"`
- Grid: `grid-cols-2 sm:3 md:4 lg:5`
- Data from `/api/recently-added-episodes`

### kelly-collection (akplex.tv/kelly/)
- **Base path:** `/kelly/`
- **API proxy:** `/capi` -> `http://localhost:5060`
- **Backend:** collection-api (Flask + plexapi)
- **Auth:** X-Kelly-Key header (access code)
- **Extra dep:** `vue-draggable-plus`
- **Custom auth gate** — inline in App.vue with Totoro GIF (do NOT replace with shared AuthGate)

---

## Tailwind Config

Each app's `tailwind.config.js` imports the shared base:
```js
import baseConfig from '../tailwind.config.js'
export default {
  ...baseConfig,
  content: [
    './index.html',
    './src/**/*.{vue,js}',
    '../packages/shared/**/*.{vue,js}'  // scan shared components for Tailwind classes
  ]
}
```

The shared base defines the dark color palette:
```
dark-900: #0a0a0f
dark-800: #12121a
dark-700: #1a1a24
```

---

## Static Sites (non-Vue)

These are plain HTML, not part of the npm workspace. Some have their own deploy.sh scripts that copy files into web-router; others (issue-report, announce, file-grabber) are bind-mounted directly so edits are live immediately.

| Directory | URL Path | Notes |
|-----------|----------|-------|
| hub-site | /request, /issues, /join | Multi-page static site |
| docker-services | /services | Docker status page |
| request-form | /request (alt) | Content request form |
| issue-report | /issues (alt) | Issue report form |
| join-request | /join (alt) | Join request form |
| announce | /announce | Admin form: set/clear the Status Hub banner. Single index.html, vanilla JS. GETs/POSTs `/api/announcement`, prompts for `X-Admin-Key`. Bind-mounted (live, no build). |

---

## Status Hub Styling Rules

**When modifying the status-hub gradient, ONLY change the background gradient. DO NOT touch foreground elements.**
- Background gradient: `bg-gradient-*` class on root div
- Section headers: `text-slate-300` (NOT pink/fuchsia), `uppercase tracking-widest`
- Section dot indicators: `bg-slate-400` (NOT pink/fuchsia)
- App cell hover glows: orange (Plex), blue (Request), red (Report Bugs)
- Fuchsia is reserved for: movie year labels, calendar air times, trending movie years
- Status dots use emerald (ok), rose (down/error), amber (degraded/missing), slate (unknown)
- Teleported modals need **unscoped** `<style>` for transition classes (`fade-enter-active`, etc.) — Vue scoped styles do NOT apply to `<Teleport>` content
- `scrollbar-hide` class (from `@webhead/shared/styles.css`) hides scrollbars on horizontal scroll sections
