# Design System UI Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the AquaSignal design-system bundle into real, documented React components in `frontend/src/components/ui/`, then recompose the existing screens onto them — same look, design system as the foundation.

**Architecture:** Add six primitive components (`Button`, `Card`, `MicroLabel`, `Badge`, `Field`, `Banner`) styled with the app's existing Tailwind tokens; relocate the three domain components that already match the bundle (`RiskScoreCard`, `SegmentedControl`, `MapLegend→RiskLegend`) into `ui/` and extract `TrendBadge`. Then convert ad-hoc utility-class markup across the screens to consume these primitives. The `api/`, `context/`, and `lib/` layers are never touched.

**Tech Stack:** React 18 + Vite + Tailwind CSS 3 (JSX, no TypeScript). TanStack Query, MapLibre, Recharts already in place.

## Global Constraints

- **Never touch** `frontend/src/api/**`, `frontend/src/context/**`, `frontend/src/lib/**`, or any `*.test.js`. No data flow, routing, auth, or backend-contract changes.
- **Risk colors come from `lib/risk.js`**, never hardcoded. Components that need a *dynamic* band color call `riskBand(score)`; static tints use the Tailwind `risk-*` tokens (which are the same contract values). Do not copy the bundle's `RISK_BANDS`/`RAMP` arrays into a component.
- **Zero visual regression.** Each primitive reproduces the exact existing classes (`.card`, `.btn-*`, `.microlabel`, the banners, the auth input). A screen looks identical before and after.
- **Preserve behavior:** ARIA roles (`alert`/`status`/`dialog`), `focus-visible:outline-water`, `prefers-reduced-motion`, the `<768px` bottom-sheet, lazy panel/recharts, `localStorage` view persistence, sign-out cache clear.
- **Verification is visual-only** (no component tests). Each task ends with: `npm run build` passes, dev server renders, screenshot looks identical, `preview_console_logs` shows no errors, and `npm test` (lib suite) stays green. Then commit on `main`.
- All components are **default exports**; the `ui/index.js` barrel re-exports them as named exports.
- Commit messages use Conventional Commits (`feat:`, `refactor:`). Commit directly on `main`.

**Verification environment note:** the dev server runs at `http://127.0.0.1:3000` (`npm run dev` in `frontend/`); data-bearing screens need the backend at `127.0.0.1:8000`. Start the backend before phases that need populated panels (Phases 3, 5). Chrome/banner/auth states (Phases 0–2, 4) render without it. Use `.claude/launch.json` server name `frontend-dev` with the preview tooling.

---

## Phase 0 — Primitives + relocation

Net-new foundation. One commit at the end of the phase (the relocation must be atomic so imports never break the build).

### Task 0.1: Create `Card` and `MicroLabel`

**Files:**
- Create: `frontend/src/components/ui/Card.jsx`
- Create: `frontend/src/components/ui/MicroLabel.jsx`

**Interfaces:**
- Produces: `Card({ children, padding=16, as='div', className='', style, ...rest })` — padding number→`${n}px`, string→verbatim. `MicroLabel({ children, as='p', className='', ...rest })`.

- [ ] **Step 1: Write `Card.jsx`**

```jsx
// Base surface of the design system: near-white card on warm paper, hairline
// ink border, soft low shadow, generous rounding. The shell for every floating
// element over the map.
export default function Card({ children, padding = 16, as: Tag = 'div', className = '', style, ...rest }) {
  const pad = typeof padding === 'number' ? `${padding}px` : padding;
  return (
    <Tag
      className={`rounded-xl border border-ink/10 bg-surface shadow-card ${className}`}
      style={{ padding: pad, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
```

- [ ] **Step 2: Write `MicroLabel.jsx`**

```jsx
// IBM Plex Mono, 10px, uppercase, wide tracking, soft ink — the connective
// tissue of the survey-ledger look (section eyebrows, field labels, captions).
export default function MicroLabel({ children, as: Tag = 'p', className = '', ...rest }) {
  return (
    <Tag className={`font-mono text-[10px] uppercase tracking-[0.18em] text-ink-soft ${className}`} {...rest}>
      {children}
    </Tag>
  );
}
```

- [ ] **Step 3:** Defer build/visual check to Task 0.9 (the barrel + imports land together).

### Task 0.2: Create `Button`

**Files:**
- Create: `frontend/src/components/ui/Button.jsx`

**Interfaces:**
- Produces: `Button({ children, variant='primary'|'secondary'|'ghost', size='sm'|'md', fullWidth=false, href, type='button', disabled=false, className='', onClick, ...rest })`. Renders `<a>` when `href` set.

- [ ] **Step 1: Write `Button.jsx`** (classes mirror `.btn-primary`/`.btn-secondary` in `index.css`; `md`=`px-4 py-2.5 text-sm`, `sm`=`px-3 py-1.5 text-xs`; `ghost` mirrors the MapPage sign-out button).

```jsx
// Primary action button tuned to the survey-ledger palette. Three variants:
// solid water `primary`, paper-bordered `secondary`, quiet `ghost`. Renders an
// <a> when `href` is given.
const BASE =
  'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors focus-visible:outline-water disabled:cursor-not-allowed disabled:opacity-50';
const SIZES = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2.5 text-sm' };
const VARIANTS = {
  primary: 'border border-transparent bg-water text-white hover:bg-water-deep',
  secondary: 'border border-ink/15 bg-surface text-ink hover:border-ink/30 hover:bg-paper',
  ghost: 'border border-transparent text-ink-soft hover:bg-paper hover:text-ink',
};

export default function Button({
  children, variant = 'primary', size = 'md', fullWidth = false,
  href, type = 'button', disabled = false, className = '', onClick, ...rest
}) {
  const cls = `${BASE} ${SIZES[size] ?? SIZES.md} ${VARIANTS[variant] ?? VARIANTS.primary} ${fullWidth ? 'w-full' : ''} ${className}`;
  if (href) {
    return (
      <a href={href} className={cls} onClick={disabled ? undefined : onClick} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <button type={type} disabled={disabled} className={cls} onClick={onClick} {...rest}>
      {children}
    </button>
  );
}
```

- [ ] **Step 2:** Defer build/visual check to Task 0.9.

### Task 0.3: Create `Badge`

**Files:**
- Create: `frontend/src/components/ui/Badge.jsx`

**Interfaces:**
- Produces: `Badge({ children, tone='neutral'|'accent'|'low'|'medium'|'high'|'critical', className='', ...rest })`.

- [ ] **Step 1: Write `Badge.jsx`** (tones mirror the bundle's `Badge.jsx`; risk tints use Tailwind `risk-*` tokens).

```jsx
// Small pill tag. `tone` picks a tinted surface: neutral, accent (water), or one
// of the four risk bands. Used for source tags, outlook chips, quick-win flags.
const TONES = {
  neutral: 'bg-surface text-ink-faint border-ink/10',
  accent: 'bg-water-wash text-water border-water/35',
  low: 'bg-risk-low/15 text-[#2E7D32] border-risk-low/40',
  medium: 'bg-risk-medium/[0.18] text-[#946200] border-risk-medium/50',
  high: 'bg-risk-high/[0.12] text-[#C2410C] border-risk-high/40',
  critical: 'bg-risk-critical/10 text-risk-critical border-risk-critical/30',
};

export default function Badge({ children, tone = 'neutral', className = '', ...rest }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold leading-snug ${TONES[tone] ?? TONES.neutral} ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 2:** Defer build/visual check to Task 0.9.

### Task 0.4: Create `Field`

**Files:**
- Create: `frontend/src/components/ui/Field.jsx`

**Interfaces:**
- Produces: `Field({ id, label, type='text', value, onChange, placeholder, hint, error, required=false, autoComplete, className='', ...rest })`. `onChange` receives the **string value**, not the event. Input classes are byte-identical to the current auth input so Phase 4 is a pure swap.

- [ ] **Step 1: Write `Field.jsx`**

```jsx
// Labelled text input: mono microlabel above a paper-bordered field, optional
// hint or error below. Matches the auth-form input exactly. onChange(value).
export default function Field({
  id, label, type = 'text', value, onChange, placeholder, hint, error,
  required = false, autoComplete, className = '', ...rest
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="microlabel">
          {label}
        </label>
      )}
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        aria-describedby={hintId}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
        className={`mt-1.5 w-full rounded-lg border bg-surface px-3.5 py-2.5 text-sm focus-visible:outline-water ${error ? 'border-risk-critical/45' : 'border-ink/15'}`}
        {...rest}
      />
      {error ? (
        <p className="mt-1.5 text-xs font-medium text-risk-critical">{error}</p>
      ) : hint ? (
        <p id={hintId} className="mt-1 text-xs text-ink-faint">{hint}</p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2:** Defer build/visual check to Task 0.9.

### Task 0.5: Create `Banner`

**Files:**
- Create: `frontend/src/components/ui/Banner.jsx`

**Interfaces:**
- Produces: `Banner({ tone='info'|'warn'|'critical', icon, children, onDismiss, actions, className='', ...rest })`. `role="alert"` for critical, else `role="status"`. Presentational only — consumers own all data/handlers.

- [ ] **Step 1: Write `Banner.jsx`** (tone classes mirror `AlertBanner` (critical), `StaleDataBanner` (warn `bg-[#FFF8E1] border-risk-medium/60`), and a quiet `info`).

```jsx
// Floating status banner over the map. `tone`: critical (solid deep-red bar,
// role=alert), warn (warm amber card), info (quiet paper card). Optional icon,
// dismiss button, and trailing actions. Presentational only.
const TONES = {
  critical: 'bg-risk-critical text-white border-risk-critical/40',
  warn: 'bg-[#FFF8E1] text-ink border-risk-medium/60',
  info: 'bg-surface text-ink border-ink/10',
};

export default function Banner({ tone = 'info', icon, children, onDismiss, actions, className = '', ...rest }) {
  return (
    <div
      role={tone === 'critical' ? 'alert' : 'status'}
      className={`pointer-events-auto flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm shadow-card animate-fade-up ${TONES[tone] ?? TONES.info} ${className}`}
      {...rest}
    >
      {icon && <span aria-hidden="true" className="shrink-0">{icon}</span>}
      <div className="min-w-0 flex-1">{children}</div>
      {actions}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="-mr-1 shrink-0 px-0.5 text-lg leading-none opacity-80 hover:opacity-100"
        >
          ×
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2:** Defer build/visual check to Task 0.9.

### Task 0.6: Extract `TrendBadge` and relocate `RiskScoreCard`

**Files:**
- Create: `frontend/src/components/ui/TrendBadge.jsx`
- Create: `frontend/src/components/ui/RiskScoreCard.jsx` (moved from `frontend/src/components/RiskScoreCard.jsx`)
- Delete: `frontend/src/components/RiskScoreCard.jsx`

**Interfaces:**
- Produces: `TrendBadge({ trend, className='' })` reading `trendInfo(trend)` from `lib/risk.js`. `RiskScoreCard({ risk, trend, month, label='Current risk' })` (unchanged contract), now importing `TrendBadge`.

- [ ] **Step 1: Write `ui/TrendBadge.jsx`** (the exact pill currently inside `RiskScoreCard`).

```jsx
import { trendInfo } from '../../lib/risk.js';

const TONES = {
  bad: 'border-risk-critical/30 bg-risk-critical/10 text-risk-critical',
  good: 'border-risk-low/40 bg-risk-low/15 text-[#2E7D32]',
  neutral: 'border-ink/15 bg-ink/5 text-ink-soft',
};

// Trend pill — ↑ worsening / → stable / ↓ improving. Shared by RiskScoreCard
// and available standalone for rows and tables.
export default function TrendBadge({ trend, className = '' }) {
  const t = trendInfo(trend);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONES[t.tone]} ${className}`}>
      <span aria-hidden="true">{t.arrow}</span> {t.label}
    </span>
  );
}
```

- [ ] **Step 2: Create `ui/RiskScoreCard.jsx`** — move the file and update imports to use `TrendBadge` and the new relative path. Full content:

```jsx
import { formatMonth, riskBand } from '../../lib/risk.js';
import TrendBadge from './TrendBadge.jsx';

/** Big colour-coded score with the trend badge beside it. */
export default function RiskScoreCard({ risk, trend, month, label = 'Current risk' }) {
  const band = riskBand(risk);

  return (
    <div
      className="overflow-hidden rounded-xl border border-ink/10"
      aria-label={`Current risk ${Number(risk).toFixed(0)} out of 100, ${band.label}.`}
    >
      <div
        className="flex items-end justify-between gap-4 px-5 py-4"
        style={{ backgroundColor: band.color, color: band.onColor }}
      >
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] opacity-80">
            {label}
          </p>
          <p className="font-mono text-5xl font-semibold leading-none tracking-tight">
            {Number(risk).toFixed(0)}
            <span className="text-xl opacity-70">/100</span>
          </p>
        </div>
        <p className="font-display text-xl font-semibold">{band.label}</p>
      </div>
      <div className="flex items-center justify-between bg-surface px-5 py-2.5">
        <TrendBadge trend={trend} />
        {month && <span className="microlabel">Scores · {formatMonth(month)}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Delete** `frontend/src/components/RiskScoreCard.jsx` (use `git mv` semantics — the new file plus deletion). Imports updated in Task 0.9.

### Task 0.7: Relocate `SegmentedControl`

**Files:**
- Create: `frontend/src/components/ui/SegmentedControl.jsx` (verbatim copy of `frontend/src/components/SegmentedControl.jsx`)
- Delete: `frontend/src/components/SegmentedControl.jsx`

- [ ] **Step 1:** Copy `SegmentedControl.jsx` unchanged into `ui/`, delete the original. (No relative-path imports inside it, so no edits needed.) Imports updated in Task 0.9.

### Task 0.8: Relocate `MapLegend` as `RiskLegend`

**Files:**
- Create: `frontend/src/components/ui/RiskLegend.jsx` (moved from `frontend/src/components/MapLegend.jsx`)
- Delete: `frontend/src/components/MapLegend.jsx`

- [ ] **Step 1:** Copy `MapLegend.jsx` into `ui/RiskLegend.jsx`, rename the function to `RiskLegend`, and fix the import path (it imports from `../lib/risk.js`; from `ui/` that becomes `../../lib/risk.js`). Default export `RiskLegend`. Delete the original.

```jsx
import { NO_DATA_COLOR, RISK_BANDS, riskRampGradient } from '../../lib/risk.js';

/** Survey-sheet style map key: a continuous ramp bar plus the named bands. */
export default function RiskLegend() {
  // ...body identical to the current MapLegend.jsx (lines 5-56)...
}
```

(Copy the body of `MapLegend.jsx` exactly; only the function name and the import path change.)

### Task 0.9: Barrel + repo-wide import updates + verify + commit

**Files:**
- Create: `frontend/src/components/ui/index.js`
- Modify: `frontend/src/pages/MapPage.jsx:10,12,94,100`
- Modify: `frontend/src/components/panel/CellDetails.jsx:7`
- Modify: `frontend/src/components/panel/DistrictDetails.jsx:16`
- Modify: `frontend/src/components/panel/MonthSnapshot.jsx:14`

- [ ] **Step 1: Write `ui/index.js`**

```js
export { default as Button } from './Button.jsx';
export { default as Card } from './Card.jsx';
export { default as MicroLabel } from './MicroLabel.jsx';
export { default as Badge } from './Badge.jsx';
export { default as Field } from './Field.jsx';
export { default as Banner } from './Banner.jsx';
export { default as SegmentedControl } from './SegmentedControl.jsx';
export { default as RiskScoreCard } from './RiskScoreCard.jsx';
export { default as TrendBadge } from './TrendBadge.jsx';
export { default as RiskLegend } from './RiskLegend.jsx';
```

- [ ] **Step 2: Update `MapPage.jsx`** — replace lines 10 and 12 imports with `import { RiskLegend, SegmentedControl } from '../components/ui';` and change `<MapLegend />` (line 94) to `<RiskLegend />`.

- [ ] **Step 3: Update the three panel imports** — in `CellDetails.jsx`, `DistrictDetails.jsx`, `MonthSnapshot.jsx`, replace `import RiskScoreCard from '../RiskScoreCard.jsx';` with `import { RiskScoreCard } from '../ui';`.

- [ ] **Step 4: Run the lib test suite** — confirm nothing logic-side broke.

Run: `cd frontend && npm test`
Expected: all existing `src/**/*.test.js` pass.

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds with no unresolved-import errors.

- [ ] **Step 6: Visual check** — start `frontend-dev`, screenshot the map screen at 1280×800, confirm the legend, view switcher, and (if backend up) a risk score card render identically. Check `preview_console_logs` (level error) is clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui frontend/src/pages/MapPage.jsx \
  frontend/src/components/panel/CellDetails.jsx \
  frontend/src/components/panel/DistrictDetails.jsx \
  frontend/src/components/panel/MonthSnapshot.jsx
git rm frontend/src/components/RiskScoreCard.jsx frontend/src/components/SegmentedControl.jsx frontend/src/components/MapLegend.jsx
git commit -m "refactor(ui): add design-system primitives and relocate shared components"
```

---

## Phase 1 — Consolidate banners onto `Banner`

Recompose the three **card-style** banners. `WarmupBanner` is intentionally **out of scope**: it is a full-bleed fixed top connection bar (solid ink, spinner), structurally unlike the floating card banners — folding it into `Banner` would regress it. Leave it untouched.

### Task 1.1: `AlertBanner` → `Banner tone="critical"`

**Files:**
- Modify: `frontend/src/components/AlertBanner.jsx`

**Interfaces:**
- Consumes: `Banner` from `./ui`. Keeps `useCriticalDistricts`, `onOpenDistrict`, and the local `dismissed` state.

- [ ] **Step 1: Rewrite the returned markup** keeping all logic (lines 1-12 unchanged). Replace the `<div role="alert">…</div>` block with:

```jsx
  return (
    <Banner
      tone="critical"
      icon="⚠"
      onDismiss={() => setDismissed(true)}
      className="flex-wrap gap-x-3 gap-y-1"
    >
      <span className="mr-2 font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
        Critical risk
      </span>
      <span className="text-sm">
        {critical.length === 1
          ? 'This province or city needs attention:'
          : 'These provinces and cities need attention:'}
      </span>
      <span className="ml-2 inline-flex flex-wrap gap-1.5">
        {critical.map((district) => (
          <button
            key={district}
            type="button"
            onClick={() => onOpenDistrict(district)}
            aria-label={`Open ${district} details`}
            className="rounded-md bg-white/15 px-2.5 py-0.5 text-sm font-semibold transition-colors hover:bg-white/30 focus-visible:outline-white"
          >
            {district}
          </button>
        ))}
      </span>
    </Banner>
  );
```

Add `import Banner from './ui/Banner.jsx';` (or `import { Banner } from './ui';`) at the top.

- [ ] **Step 2: Verify** — with the backend up and a subscribed critical district (or via a temporary mock), confirm the critical banner looks identical: deep-red bar, ⚠ icon, district pills, dismiss ×. Screenshot. Console clean. `npm test` green.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build AlertBanner on the Banner primitive"`.

### Task 1.2: `StaleDataBanner` → `Banner tone="warn"`

**Files:**
- Modify: `frontend/src/components/StaleDataBanner.jsx`

- [ ] **Step 1: Rewrite the return** (keep the `fetchedTime` computation, lines 6-9) as:

```jsx
  return (
    <Banner tone="warn" icon="⚠️" actions={
      <button
        type="button"
        onClick={onRetry}
        aria-label="Retry loading latest data"
        className="rounded-md border border-ink/15 bg-surface px-3 py-1 text-xs font-semibold hover:bg-paper"
      >
        Retry
      </button>
    }>
      <p className="text-sm font-medium">
        Data unavailable — showing last cached data
        {fetchedTime && <span className="text-ink-soft"> (fetched {fetchedTime})</span>}
      </p>
    </Banner>
  );
```

Add the `Banner` import.

- [ ] **Step 2: Verify** — trigger the stale state (backend up, then stop it and refetch, or mock `isError && data`). Confirm amber card, ⚠️, Retry button identical. Screenshot. Console clean. `npm test` green.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build StaleDataBanner on the Banner primitive"`.

### Task 1.3: `SessionExpiryNotice` (inline in MapPage) → `Banner tone="warn"`

**Files:**
- Modify: `frontend/src/pages/MapPage.jsx` (the `SessionExpiryNotice` function, lines 172-189)

- [ ] **Step 1: Replace** the `SessionExpiryNotice` function body's returned `<div role="status">…</div>` with a `Banner`:

```jsx
function SessionExpiryNotice({ onSignIn }) {
  return (
    <Banner tone="warn" icon="⏳" actions={
      <button
        type="button"
        onClick={onSignIn}
        className="rounded-md border border-ink/15 bg-surface px-3 py-1 text-xs font-semibold hover:bg-paper"
      >
        Sign in again
      </button>
    }>
      <p className="text-sm font-medium">Your session expires soon.</p>
    </Banner>
  );
}
```

Add `Banner` to the `../components/ui` import in MapPage.

- [ ] **Step 2: Verify** — render with `isExpiring` true (mock the auth hook or set a near-expiry token). Confirm identical. Screenshot. Console clean.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build the session-expiry notice on Banner"`.

---

## Phase 2 — MapPage chrome onto primitives

### Task 2.1: `Brand`, `StatusCard`, `HardError` → `Card`/`Button`/`MicroLabel`

**Files:**
- Modify: `frontend/src/pages/MapPage.jsx` (the `Brand` (112-124), `StatusCard` (126-170), and `HardError` (191-208) functions)

**Interfaces:**
- Consumes: `Card`, `Button`, `MicroLabel` from `../components/ui`.

- [ ] **Step 1: `Brand`** — swap the outer `<div className="pointer-events-auto card …">` for `<Card>` and the microlabel `<p>` for `<MicroLabel>`:

```jsx
function Brand() {
  return (
    <Card padding="8px 14px" className="pointer-events-auto flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden="true">
        <path d="M16 3c5 7 9 11.5 9 17a9 9 0 1 1-18 0c0-5.5 4-10 9-17z" fill="#0E6E83" />
      </svg>
      <div>
        <p className="font-display text-base font-bold leading-none">AquaSignal</p>
        <MicroLabel className="mt-0.5 hidden sm:block">Groundwater survey · Mekong Delta</MicroLabel>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: `StatusCard`** — outer becomes `<Card padding="8px 12px" className="pointer-events-auto flex items-center gap-2 sm:gap-3">`; the month/fetched `<p className="microlabel">` becomes `<MicroLabel>`; the Refresh and Sign-in buttons become `<Button variant="secondary" size="sm">`, and Sign-out becomes `<Button variant="ghost" size="sm">`. Keep all handlers/props (`onRefresh`, `isFetching`, `onSignIn`, `onSignOut`) and the spinner span exactly. Example for Refresh:

```jsx
<Button variant="secondary" size="sm" onClick={onRefresh} disabled={isFetching} aria-label="Refresh risk data">
  <span className={isFetching ? 'inline-block animate-spin' : ''} aria-hidden="true">⟳</span>
  {isFetching ? 'Updating…' : 'Refresh'}
</Button>
```

- [ ] **Step 3: `HardError`** — outer card `<div className="card max-w-md p-6 …">` becomes `<Card className="max-w-md text-center animate-fade-up" padding={24} role="alert">`; the "Try again" `<button className="btn-primary mt-5">` becomes `<Button className="mt-5" onClick={onRetry}>Try again</Button>`. Keep the `detail` logic.

- [ ] **Step 4: Verify** — screenshot the top chrome (brand chip + status card) at 1280; toggle sign-in/out to confirm button variants; force the hard-error overlay (stop backend, clear cache) to confirm it's identical. Console clean. `npm test` green.

- [ ] **Step 5: Commit** — `git commit -m "refactor(ui): build MapPage chrome on Card/Button/MicroLabel"`.

---

## Phase 3 — Detail panel + DistrictDetails

Start the backend first (these screens need data). Verify both the desktop right-dock and the `<768px` bottom sheet.

### Task 3.1: `DistrictPanel` header → `Button`/`MicroLabel`

**Files:**
- Modify: `frontend/src/components/DistrictPanel.jsx` (header block lines 66-81)

- [ ] **Step 1:** Replace the subtitle `<p className="microlabel mt-1">` with `<MicroLabel className="mt-1">`, and the close `<button>` (lines 73-80) with `<Button variant="ghost" size="sm" onClick={onClose} aria-label="Close detail panel" className="shrink-0 !px-2.5 text-lg leading-none">×</Button>`. Add the `../components/ui` import. Leave the `<aside>` shell, the grab handle, and all state logic untouched.

- [ ] **Step 2: Verify** — open a district panel; confirm the header title, subtitle eyebrow, and close button look/behave identically on desktop dock and mobile sheet (`preview_resize` mobile 375). Console clean.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build the detail-panel header on primitives"`.

### Task 3.2: `DistrictDetails` CTAs + section titles → `Button`/`MicroLabel`

**Files:**
- Modify: `frontend/src/components/panel/DistrictDetails.jsx`
- Modify: `frontend/src/components/panel/SectionTitle.jsx`

- [ ] **Step 1: `SectionTitle`** — rebuild on `MicroLabel` (preserve the `<h3>` semantics and `mb-2.5`):

```jsx
import MicroLabel from '../ui/MicroLabel.jsx';

export default function SectionTitle({ children }) {
  return <MicroLabel as="h3" className="mb-2.5">{children}</MicroLabel>;
}
```

- [ ] **Step 2: `DistrictDetails`** — replace the "Plan your water use with AI" `<button>` (lines 59-66) with a `Button` that keeps the accent-tinted look, and the inline "See history" `<button>` (lines 72-80) with a `Button variant="secondary" size="sm"`:

```jsx
<Button
  variant="secondary"
  fullWidth
  onClick={onPlanWithAi}
  className="border-water/40 bg-water/10 text-water hover:bg-water/15"
>
  <span aria-hidden="true">✦</span> Plan your water use with AI
</Button>
```

```jsx
<Button variant="secondary" size="sm" onClick={onSeeHistory} className="shrink-0">
  See history <span aria-hidden="true">→</span>
</Button>
```

Add the `../ui` import. The `microlabel` `<h3>` for "6-month outlook" (line 70) becomes `<MicroLabel as="h3">`. Leave all hooks and section structure intact.

- [ ] **Step 3: Verify** — open a district with the advisor enabled; confirm the AI CTA (accent tint), the See-history button, and every section eyebrow render identically; click both CTAs to confirm the popouts still open. Screenshot desktop + mobile. Console clean. `npm test` green.

- [ ] **Step 4: Commit** — `git commit -m "refactor(ui): build DistrictDetails CTAs and section titles on primitives"`.

---

## Phase 4 — Auth forms onto `Field`

### Task 4.1: `AuthForms` → shared `Field`

**Files:**
- Modify: `frontend/src/components/auth/AuthForms.jsx`

- [ ] **Step 1:** Add `import Field from '../ui/Field.jsx';` (or `import { Field } from '../ui';`). **Delete** the local `Field` function (lines 176-199). Add `required` to the email and password `<Field>` usages (they were `required` via `type !== 'text'`): set `required` on `signin-email`, `signin-password`, `register-email`, `register-password`, `register-confirm`; leave `register-name` optional. The `hint` prop on the password field already matches the shared `Field` API.

- [ ] **Step 2: Verify** — open the auth modal (tap "Sign in"); confirm both forms render identically (mono labels, paper inputs, hint line under password). Submit with a bad password to confirm `FormError` still shows. Toggle sign-in/register. Screenshot. Console clean. `npm test` green.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build auth forms on the Field primitive"`.

---

## Phase 5 — Advisor flow onto primitives

Backend up. The advisor flow lives in `frontend/src/components/panel/AdvisorPlanner.jsx`, `SiteProfileForm.jsx`, `ReportView.jsx`, and the chart pieces under `panel/charts/`. The bundle's `ui_kits/risk-map/advisor-report.html` is the visual reference for the target composition (goal picker, site form, report with allocation donut + scored priority actions + `AI estimate` source tags).

### Task 5.1: Goal picker + site form → `Card`/`Badge`/`Button`/`Field`

**Files:**
- Modify: `frontend/src/components/panel/AdvisorPlanner.jsx`
- Modify: `frontend/src/components/panel/SiteProfileForm.jsx`

- [ ] **Step 1:** Read both files. Apply the established swaps: wrapping surfaces → `Card`; step/source chips → `Badge` (tone `accent`); intake inputs → `Field` (with `onChange(value)`); back/generate/submit buttons → `Button` (variant `ghost` for back, `primary` for generate). Preserve every hook, the question-fetch/report-fetch calls, loading/submitting states, and copy.

- [ ] **Step 2: Verify** — run the full advisor flow against the backend (pick a goal → answer the intake → generate). Confirm each step renders identically and the report still streams. Screenshot each step. Console clean. `npm test` green.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build advisor goal picker and site form on primitives"`.

### Task 5.2: Report view → `Card`/`Badge`/`Button`/`MicroLabel`

**Files:**
- Modify: `frontend/src/components/panel/ReportView.jsx`
- Modify (as needed): `frontend/src/components/panel/charts/AllocationDonut.jsx`, `frontend/src/components/panel/charts/PriorityActions.jsx`

- [ ] **Step 1:** Read `ReportView.jsx` and the two chart pieces. Swap: section eyebrows → `MicroLabel`; the `AI estimate` / `calculated` source tags and the outlook + quick-win chips → `Badge`; Copy/Export buttons → `Button`; wrapping report surfaces → `Card`. Keep the allocation donut and priority-action scoring logic exactly — only the surrounding chrome and tags change. Do not alter any data shape.

- [ ] **Step 2: Verify** — view a generated report; confirm headline, outlook badge, situation/findings, allocation donut, scored priority actions (impact/effort pips, quick-win flag), source tags, and the Copy/Export PDF buttons all render identically and PDF export still works. Screenshot full report. Console clean. `npm test` green.

- [ ] **Step 3: Commit** — `git commit -m "refactor(ui): build the advisor report view on primitives"`.

---

## Done criteria

- Six primitives + `TrendBadge` live in `frontend/src/components/ui/`, re-exported from `ui/index.js`.
- The three relocated domain components import from `../../lib/risk.js` and are consumed via the barrel.
- All four banner surfaces (three on `Banner`, `WarmupBanner` left as-is) and the MapPage chrome, detail panel, auth forms, and advisor flow consume primitives instead of ad-hoc markup.
- `api/`, `context/`, `lib/`, and all `*.test.js` are unchanged; `npm test` is green.
- Every phase screenshot-verified identical, each committed on `main`.
