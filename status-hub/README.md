# Status Hub

Public-facing status page for WebHead Media, accessible at `akplex.tv/status/`.

## Tech Stack

- **Vue 3** - Composition API with `<script setup>`
- **Vite** - Build tool with HMR for development
- **Tailwind CSS** - Utility-first styling (built, not CDN)

## Project Structure

```
status-hub/
├── dist/                  # Built output (served in production)
├── public/
│   └── images/            # Static assets copied as-is
├── src/
│   ├── assets/            # Images imported by Vue (hashed in build)
│   ├── App.vue            # Main application component
│   ├── main.js            # Vue app entry point
│   └── style.css          # Tailwind directives
├── index.html             # Vite entry point
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── deploy.sh              # Build script
└── announcements.json     # Announcement data (used by API)
```

## Development

### Prerequisites

**On the tower:** Docker (node/npm NOT installed on system)
**For local development:** Node.js 18+ and npm

### Setup

**Tower deployment:** No setup needed, `./deploy.sh` handles everything via Docker

**Local development:**
```bash
cd ~/DockerApps/websites/status-hub
npm install
```

### Dev Server with Hot Reload (Local Development Only)

**This requires npm/node installed locally, not available on the tower.**

```bash
npm run dev
```

Opens at `http://localhost:5173/status/` with live reload on file changes.

**Note:** The dev server proxies `/api` requests to `localhost:5000`. If the announcement-api container runs on a different port, update `vite.config.js`.

### Build for Production

**On tower (use Docker):**
```bash
docker run --rm -v "$(pwd):/app" -w /app node:22-alpine npm run build
```

**Local machine (with npm installed):**
```bash
npm run build
```

Output goes to `dist/` which is volume-mounted by the web-router container.

## Deployment

**IMPORTANT: Node/npm is NOT installed on the tower system.**

The `dist/` folder is mounted directly into the web-router container at `/usr/share/nginx/html/status/`. No manual copying is required.

### Deploy Changes

```bash
./deploy.sh
```

This script uses a Docker container (node:22-alpine) to run the build since npm/node is not installed on the tower. The built files go directly to `dist/` and are immediately live.

### Manual Build (if needed)

```bash
cd ~/DockerApps/websites/status-hub
docker run --rm -v "$(pwd):/app" -w /app node:22-alpine sh -c "npm install --silent && npm run build"
```

## Styling Guidelines

### CRITICAL: Background Gradient vs Foreground Elements

**The background gradient is SEPARATE from all other styling. Do NOT change foreground elements when modifying the gradient.**

- **Background gradient**: The `bg-gradient-*` class on the root `<div>` (line 290 in App.vue)
  - This is ONLY the page background
  - Treat it like a background image
  - Changing this should NEVER affect text colors, element styles, hover effects, etc.

- **Foreground elements**: Everything else (cards, text, buttons, icons, etc.)
  - Text colors (e.g., section headers should be `text-slate-300`, NOT pink/fuchsia)
  - Card styles, hover effects, borders
  - Icon colors and indicators
  - These are INDEPENDENT of the background gradient

**Example of what NOT to do:**
- Changing the gradient from purple to pink, then also changing all text to pink ❌
- The gradient is the canvas, everything else is painted on top ✅

**Current gradient** (as of Feb 2026):
```
bg-gradient-to-b from-indigo-950 via-purple-900/60 via-20% via-fuchsia-900/50 via-40% via-pink-900/40 via-60% via-orange-900/30 via-80% to-slate-950
```

## Configuration

### Announcements

Edit `announcements.json` to display a banner:

```json
{
  "enabled": true,
  "message": "Scheduled maintenance tonight at 2 AM",
  "severity": "yellow",
  "dismissible": true
}
```

Severity options: `red`, `yellow`, `green`, `info`

### Services and Tools

Edit the arrays in `src/App.vue`:

```javascript
const services = [
  { name: "AK's Plex", href: 'https://app.plex.tv', icon: '...' },
  // ...
]

const tools = [
  { name: 'Tautulli', href: 'https://tautulli.akplex.tv', icon: '...' },
  // ...
]
```

For local images, import them at the top of the script and use the variable.

### Custom Colors

The dark theme colors are defined in `tailwind.config.js`:

```javascript
colors: {
  dark: {
    900: '#0a0a0f',  // Background
    800: '#12121a',  // Cards
    700: '#1a1a24'   // Hover states
  }
}
```

## API Endpoints

The page fetches from these endpoints (proxied through nginx):

| Endpoint | Purpose |
|----------|---------|
| `/api/announcement` | Announcement banner data |
| `/api/tautulli-stats` | Live stream count and bandwidth |

These are served by the `announcement-api` container defined in the web-routing stack.

## Volume Mount

Defined in `~/DockerApps/web-routing/docker-compose.yml`:

```yaml
volumes:
  - /home/anthony/DockerApps/websites/status-hub/dist:/usr/share/nginx/html/status:ro
```

The `:ro` flag makes it read-only inside the container.
