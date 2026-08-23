# Helios Investments — Dashboard UI Technical Specification

A prompt-ready design spec for a dark, glassmorphic fintech/investment dashboard. Copy this whole document to a coding agent (Claude Code, Cursor, etc.) along with "build this exact UI, adapted for [your project]."

---

## 1. Design Language Summary

- **Style**: Dark-mode glassmorphism, low-saturation neutrals + a single vivid magenta/pink accent
- **Mood**: Premium, data-forward, minimal chrome, soft ambient glow
- **Grid**: 3-column dashboard shell — fixed left sidebar, fluid main content, no right rail (right rail content is inline in main grid)
- **Corner radius**: consistently large (16–24px) — every card, button, pill, avatar uses rounded geometry, nothing sharp
- **Depth**: achieved via subtle background gradients + translucency + soft shadows, NOT hard borders or drop shadows

---

## 2. Color Tokens

```css
:root {
  /* Base surfaces */
  --bg-app: #0e0a12;              /* outermost background, near-black with purple undertone */
  --bg-sidebar: #150f1a;          /* sidebar, marginally lighter than app bg */
  --bg-card: #1c1622;             /* base card fill */
  --bg-card-glass: rgba(255, 255, 255, 0.04); /* glass overlay on top of gradient cards */

  /* Card gradients (each card has a subtle radial/linear tint, not flat fill) */
  --gradient-purple-card: linear-gradient(160deg, #2a1f35 0%, #1a1420 100%);
  --gradient-pink-glow: radial-gradient(circle at 30% 20%, rgba(230, 90, 160, 0.25), transparent 60%);

  /* Accent (primary brand / CTA / active states) */
  --accent-pink: #e05c9a;         /* primary magenta-pink */
  --accent-pink-soft: #f0a8c8;    /* lighter tint, used in gradients/highlights */
  --accent-pink-muted: rgba(224, 92, 154, 0.15); /* pill backgrounds, active nav bg */

  /* Chart line accent */
  --chart-line: #e79bd0;
  --chart-fill-top: rgba(224, 92, 154, 0.35);
  --chart-fill-bottom: rgba(224, 92, 154, 0);

  /* Semantic (gain/loss) */
  --positive: #7ee0a8;            /* soft mint green for % gains */
  --negative: #f28b8b;            /* soft coral red for % losses */

  /* Text */
  --text-primary: #f5f3f7;        /* headings, key numbers — near white */
  --text-secondary: #a89db0;      /* labels, sub-text, muted body copy */
  --text-tertiary: #6f6579;       /* faint captions, placeholder text */

  /* Borders / dividers */
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-card: rgba(255, 255, 255, 0.08);
}
```

**Palette rationale**: near-black eggplant base (#0e0a12) keeps contrast high without pure black; the single accent (pink #e05c9a) is used sparingly — active nav pill, CTA button, chart line, highlighted data point — so it reads as intentional rather than decorative.

---

## 3. Typography

```css
--font-display: 'General Sans', 'Inter', -apple-system, sans-serif; /* headings, big numbers */
--font-body: 'Inter', -apple-system, sans-serif;                    /* labels, body */

/* Scale */
--text-2xl: 28px;  /* "$12,304.11" total holding number */
--text-xl:  20px;  /* "Welcome, Nadia" greeting, card values like "$1,721.3" */
--text-lg:  16px;  /* section headers: "Watchlist", "My Portfolio" */
--text-base: 14px; /* nav items, body copy, stock names */
--text-sm:  12px;  /* tickers ("NYSE SPOT"), timestamps, chip labels */
--text-xs:  11px;  /* axis labels on chart */

/* Weights */
--weight-bold: 700;    /* big numbers, user name */
--weight-semibold: 600; /* card titles, nav active item */
--weight-medium: 500;   /* body, nav inactive */
--weight-regular: 400;  /* secondary/muted text */
```

- Numbers (prices, holdings) always **bold**, slightly larger than surrounding label text, tabular/monospaced-leaning proportions for alignment.
- Greeting text uses two weights inline: "Welcome, **Nadia**" — regular for "Welcome," bold/colored for the name.

---

## 4. Layout Grid

```css
.dashboard-shell {
  display: grid;
  grid-template-columns: 240px 1fr; /* sidebar | main */
  min-height: 100vh;
  background: var(--bg-app);
  gap: 0;
}

.main-content {
  padding: 32px 40px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Top row: header (greeting + search + avatar) */
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Second row: 3-column card grid */
.card-grid-row {
  display: grid;
  grid-template-columns: 1.1fr 1.3fr 1.1fr; /* Total Holding | Watchlist | My Portfolio */
  gap: 20px;
  align-items: stretch;
}

/* My Portfolio inner grid: 2x2 mini stat cards */
.portfolio-mini-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* Bottom: full-width chart card */
.chart-card {
  width: 100%;
  min-height: 320px;
}
```

---

## 5. Sidebar Component

```css
.sidebar {
  background: var(--bg-sidebar);
  padding: 28px 20px;
  display: flex;
  flex-direction: column;
  gap: 32px;
  border-right: 1px solid var(--border-subtle);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: var(--weight-semibold);
  font-size: var(--text-base);
}
.sidebar-logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--gradient-purple-card);
  display: grid;
  place-items: center;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: 12px;
  font-size: var(--text-base);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.nav-item:hover {
  background: rgba(255,255,255,0.03);
  color: var(--text-primary);
}
.nav-item--active {
  background: var(--gradient-purple-card); /* raised pill, slightly lighter than sidebar bg */
  color: var(--text-primary);
  font-weight: var(--weight-semibold);
  box-shadow: 0 4px 16px rgba(224, 92, 154, 0.08);
}

.nav-footer {
  margin-top: auto; /* pushes Settings/Support to bottom */
  display: flex;
  flex-direction: column;
  gap: 4px;
}
```

Icons: 18–20px line icons (Lucide/Feather style, 1.5px stroke), muted color inactive → primary color active.

---

## 6. Header Row

```css
.greeting h1 {
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
}
.greeting h1 .user-name { color: var(--accent-pink-soft); }
.greeting p {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-top: 2px;
}

.header-actions { display: flex; align-items: center; gap: 16px; }

.icon-button {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  display: grid;
  place-items: center;
}
.icon-button--has-dot::after {
  content: '';
  position: absolute;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent-pink);
  top: 8px; right: 8px;
}

.avatar-block {
  display: flex; align-items: center; gap: 10px;
}
.avatar-block img {
  width: 40px; height: 40px;
  border-radius: 50%;
  object-fit: cover;
}
.avatar-block .name { font-size: 13px; font-weight: var(--weight-semibold); }
.avatar-block .email { font-size: 11px; color: var(--text-tertiary); }
```

---

## 7. Tab Pills (Market / Wallet / Tools)

```css
.tab-group {
  display: inline-flex;
  background: var(--bg-card);
  border-radius: 14px;
  padding: 4px;
  gap: 4px;
}
.tab {
  padding: 8px 18px;
  border-radius: 10px;
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--text-secondary);
}
.tab--active {
  background: linear-gradient(135deg, var(--accent-pink), #b05c9a);
  color: #fff;
  font-weight: var(--weight-semibold);
}
```

Same pill pattern reused for the chart's time-range selector (1D/1W/1M/6M/1Y) — active state pill fills solid pink, inactive are transparent text-only buttons in a row.

---

## 8. Card Base (glassmorphism)

```css
.card {
  background: var(--gradient-purple-card);
  border: 1px solid var(--border-card);
  border-radius: 20px;
  padding: 20px;
  position: relative;
  overflow: hidden;
}

/* Ambient glow pseudo-element, common to every card */
.card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--gradient-pink-glow);
  pointer-events: none;
  opacity: 0.6;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.card-title {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--weight-medium);
}
.card-link {
  font-size: 12px;
  color: var(--accent-pink-soft);
  display: flex; align-items: center; gap: 4px;
}
```

### 8a. Total Holding Card
- Card title row: label "Total Holding" (left) + small dropdown pill "6M ▾" (right, `background: var(--bg-card-glass)`, `border-radius: 999px`, `padding: 4px 10px`)
- Big number below: `font-size: 28px; font-weight: 700; color: var(--text-primary)`
- Beneath the number: a promo sub-card ("Decisions Powered by Data") stacked inside the same card — smaller nested block with its own subtle bg, short heading + 1-line description + a solid pink pill CTA button ("Explore AI Insights")

```css
.cta-button {
  background: var(--accent-pink);
  color: #1a0e14;
  font-weight: var(--weight-semibold);
  font-size: 13px;
  padding: 10px 18px;
  border-radius: 12px;
  border: none;
}
```

### 8b. Watchlist Card
- Header: "Watchlist" title + filter pill group ("Most Viewed" active / "Gain" / "Lose" inactive, small pill-tab style, smaller than main tabs — `padding: 5px 12px; font-size: 11px`)
- List of 4 rows, each:
```css
.watchlist-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle); /* omit on last child */
}
.watchlist-row .ticker-icon {
  width: 32px; height: 32px;
  border-radius: 8px;
  display: grid; place-items: center;
  background: rgba(255,255,255,0.06);
}
.watchlist-row .name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.watchlist-row .exchange { font-size: 11px; color: var(--text-tertiary); }
.watchlist-row .price { font-size: 13px; font-weight: 600; text-align: right; }
.watchlist-row .change { font-size: 11px; text-align: right; }
.watchlist-row .change--up { color: var(--positive); }
.watchlist-row .change--down { color: var(--negative); }
```

### 8c. My Portfolio Card
- Header: "My Portfolio" title + "See all ↗" link
- 2×2 grid (`.portfolio-mini-grid`) of identical mini stat blocks:
```css
.mini-stat {
  background: rgba(255,255,255,0.03);
  border-radius: 14px;
  padding: 12px;
}
.mini-stat .icon { width: 24px; height: 24px; margin-bottom: 8px; }
.mini-stat .value { font-size: 15px; font-weight: 700; }
.mini-stat .change { font-size: 11px; color: var(--positive); margin-bottom: 6px; }
.mini-stat .meta { font-size: 10px; color: var(--text-tertiary); display: flex; justify-content: space-between; }
```
Each block: ticker icon top-left, dollar value, % change (green), then footer row with ticker symbol + "Units NN" count.

---

## 9. Chart Card (Portfolio Performance)

```css
.chart-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.chart-title { font-size: 15px; font-weight: 600; }
.range-tabs { display: flex; gap: 4px; } /* 1D 1W 1M 6M 1Y, reuse .tab pattern, smaller */
```

**Chart implementation (use Recharts `AreaChart`):**
```jsx
<AreaChart data={data}>
  <defs>
    <linearGradient id="fillPink" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="#e05c9a" stopOpacity={0.35} />
      <stop offset="100%" stopColor="#e05c9a" stopOpacity={0} />
    </linearGradient>
  </defs>
  <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
  <XAxis dataKey="month" axisLine={false} tickLine={false}
         tick={{ fill: '#6f6579', fontSize: 11 }} />
  <YAxis axisLine={false} tickLine={false}
         tick={{ fill: '#6f6579', fontSize: 11 }}
         tickFormatter={(v) => `${v/1000}k`} />
  <Area type="monotone" dataKey="value" stroke="#e79bd0" strokeWidth={2}
        fill="url(#fillPink)" />
  <Tooltip content={<CustomTooltip />} />
</AreaChart>
```

- Line: smooth monotone curve, 2px stroke, no dot markers except on hover/active point
- Active data point: shown with a small filled circle (pink, white ring) + vertical dashed guide line down to x-axis
- Custom tooltip: floating dark card (`background: #241b2c`, `border-radius: 10px`, `padding: 10px 14px`, subtle border) showing date, dollar value (bold, large), and a small green "+X%" pill
- Y-axis: gridless, labels only at 50k/100k/150k/200k intervals, muted gray, no axis line
- X-axis: month abbreviations Jan–Dec, no axis line, no tick marks

---

## 10. Spacing System

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
```
- Card internal padding: 20px
- Gap between top-level cards: 20px
- Gap between page sections (header → cards → chart): 24px
- Page outer padding: 40px horizontal, 32px vertical

---

## 11. Elevation / Effects

```css
--shadow-card: 0 8px 32px rgba(0, 0, 0, 0.35);
--shadow-cta: 0 6px 20px rgba(224, 92, 154, 0.3);
--blur-glass: blur(20px); /* if using true backdrop-filter glass panels over a background image/gradient mesh */
```
- Background of the whole app can optionally use a large, very soft radial gradient mesh (purple/pink blobs at low opacity) behind everything, with `filter: blur(80px)`, to give the ambient glow seen bleeding from card edges.
- No hard drop shadows anywhere — everything is soft, large-radius, low-opacity.

---

## 12. Responsive Notes (for the agent to implement, even though source is desktop-only)
- **≥1280px**: as specified (sidebar + 3-col card row)
- **768–1279px**: collapse `.card-grid-row` to 2 columns (Total Holding + Watchlist row 1, My Portfolio full-width row 2); sidebar becomes icon-only (64px wide, labels hidden)
- **<768px**: sidebar becomes a bottom tab bar or off-canvas drawer; all cards stack single-column; chart card retains full width with horizontal scroll on x-axis if needed

---

## 13. Prompt Block for Coding Agent

Paste this as the actual instruction after the spec above:

> Build this dashboard using [React + Tailwind / plain HTML-CSS / your stack]. Use the color tokens, typography scale, spacing system, and component CSS exactly as specified in sections 2–11. Use Recharts (or equivalent) for the area chart per section 9. Replace placeholder content (user name, portfolio values, watchlist tickers) with [your project's real data model], keeping every visual token identical. Ensure keyboard focus states are visible on all interactive elements (nav items, tabs, buttons) and respect `prefers-reduced-motion` for any transitions.
