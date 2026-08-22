# Rakshak Dashboard — Redesign Handoff

**What's in this folder**

```
handoff/
├── preview.html                    ← Open this in a browser to SEE the finished design
├── INSTRUCTIONS.md                 ← You are here
├── static/
│   ├── css/dashboard.css           ← New stylesheet (replaces frontend/static/css/dashboard.css)
│   ├── js/dashboard.js             ← Sparkline renderer (append to your existing dashboard.js OR keep separate)
│   └── images/bg-station.png       ← Background image
└── templates/
    ├── base.html                   ← New sidebar/base template (replaces frontend/templates/base.html)
    └── dashboard.html              ← New dashboard content (replaces frontend/templates/dashboard.html)
```

Everything is **plain HTML + CSS + vanilla JS**. No React, no build step. All Django template tags in the two files inside `templates/` (`{% ... %}`, `{{ ... }}`, `{% url ... %}`, `{% static ... %}`) are preserved and hooked to the same variable names your views already provide (`kpi.*`, `critical_alerts`, `track_sections`, `recent_readings`, `operator_activity`, `nav_items`, `request.user`, etc.). If a variable name in your views differs, only the small span/loop touching it needs updating — layout stays.

---

## Step-by-step for the coding agent

Do these in order. Every step is a copy/replace — nothing is generated.

### 1. Copy files into the Django app

From the ZIP root, place files at these paths inside your repo:

| From (ZIP) | To (repo) |
|---|---|
| `handoff/static/css/dashboard.css` | `frontend/static/css/dashboard.css` **(overwrite)** |
| `handoff/static/js/dashboard.js` | `frontend/static/js/dashboard.js` **(overwrite — see step 4 if you have existing JS you want to keep)** |
| `handoff/static/images/bg-station.png` | `frontend/static/images/bg-station.png` **(new file — create the `images/` folder if it doesn't exist)** |
| `handoff/templates/base.html` | `frontend/templates/base.html` **(overwrite)** |
| `handoff/templates/dashboard.html` | `frontend/templates/dashboard.html` **(overwrite)** |

### 2. Bump the cache-buster

In the new `base.html`, the `<link>` and `<script>` tags reference the stylesheet and JS with `?v=7`. If your project already uses a different scheme, keep it — just bump the number so the browser fetches the new file.

### 3. Verify the background image path

`dashboard.css` references the background image with a **CSS-relative** URL:

```css
background: url("../images/bg-station.png") center/cover no-repeat fixed;
```

That resolves from `static/css/dashboard.css` → `static/images/bg-station.png`. If your `STATIC_URL` layout is different (e.g. app-scoped static), move the image accordingly and update the CSS URL to match. Django's `collectstatic` will pick it up automatically at build time.

### 4. If your `dashboard.js` has existing logic you must keep

`handoff/static/js/dashboard.js` only renders the sparkline charts and the theme-card active state. Your existing `frontend/static/js/dashboard.js` likely has Chart.js setup, Leaflet map init, KPI count-up animations, chart-expansion modal, etc. **Do not overwrite** — instead, **append** the contents of `handoff/static/js/dashboard.js` to the bottom of your existing file.

The sparkline blocks in the new `dashboard.html` use `data-spark data-values="..."` divs. Your existing Chart.js `<canvas id="chart-vibration">` etc. is **not** used by the new design. If you need real Chart.js charts instead of the static sparklines, replace each sparkline `<div data-spark ...>` with a `<canvas>` and re-wire your Chart.js code — otherwise the new sparklines just work.

### 5. If Leaflet map should render inside the placeholder

The map card contains:

```html
<div class="map-frame" id="dashboard-map"> … placeholder text … </div>
```

Your existing map-init JS looks for `#dashboard-map`. Once your JS runs, it will paint the Leaflet map inside that container. Remove the placeholder `<div style="text-align:center;…">…</div>` from `dashboard.html` once the real map loads (or hide it via CSS when `.leaflet-container` is a descendant of `#dashboard-map`).

### 6. Template variable name check

The new `dashboard.html` reads these context vars from your view (unchanged from the original):

- `kpi.overall_health`, `kpi.active_alerts`, `kpi.predicted_failures`, `kpi.cost_savings`, `kpi.tracks_monitored`
- `critical_alerts` (list; each has `severity`, `track_id`, `title`, `description`, `time_ago`, `alert_code`)
- `track_sections` (list; each has `id`, `section`, `zone`, `health`, `status`, `trains_daily`, `maintenance_due`, `last_inspection`)
- `recent_readings`, `operator_activity`, `sensor_trends_json`
- `nav_items` (list of `{name, url, icon, active}`)
- `request.user.username`, `is_controller`

If any of your view variables have different names, do a find/replace in `dashboard.html` — nothing else needs touching.

### 7. Test locally

```bash
cd backend
python manage.py collectstatic --noinput   # if you use collectstatic in dev
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. You should see:

- Dark station image behind everything
- Glass cards with blur + gold/emerald accents
- Sparklines rendering in the four telemetry tiles
- KPI strip populated from your DB
- Track Health table with real rows
- Sensor Logs / Operator Activity feed

### 8. Commit + push

```bash
git add frontend/
git commit -m "Redesign dashboard: glassmorphic emerald + gold theme with station background"
git push
```

---

## Rollback

If anything breaks and you need the old UI back:

```bash
git checkout HEAD -- frontend/templates/dashboard.html frontend/templates/base.html frontend/static/css/dashboard.css frontend/static/js/dashboard.js
git clean -fd frontend/static/images/
```

---

## Notes / gotchas

- **Safari support**: both `backdrop-filter` and `-webkit-backdrop-filter` are set in the CSS. Do not strip one.
- **Firefox older than 103**: `backdrop-filter` support is behind a flag on some versions. The design degrades to a semi-opaque card (still readable, less glass).
- **RGB wheel & sliders in the Settings card are visual mockups** — they don't actually change the theme yet. When you want real theme switching, wire the `.theme-card` clicks to set a `data-theme` attribute on `<html>` and add matching CSS variable overrides.
- The five color CSS custom properties that drive the whole theme live in `dashboard.css` at the top (`--gold`, `--gold-soft`, `--gold-deep`, `--emerald`, `--emerald-soft`, `--charcoal`). Change those to retheme everything.
