# Design: Port the AquaSignal design system into the frontend (Approach A)

- **Date:** 2026-06-22
- **Status:** Approved design — pending spec review
- **Topic:** Make the AquaSignal "design system" bundle real in the codebase by
  introducing its component primitives and recomposing the screens onto them.

## Context

A self-contained **AquaSignal Design System** bundle (in
`C:\Users\dell\Downloads\AquaSignal Design System`) was reverse-engineered from
this repo's `frontend/`. At the token level the app already matches it exactly:
`frontend/tailwind.config.js` + `src/index.css` encode the same palette
(paper/ink/water + the fixed risk bands), the same three font families, the same
`card`/`microlabel`/`btn-*` helpers, and the same animations. The bundle's two
`ui_kits/*.html` mockups are *simplified static recreations* of screens the live
app already ships in fuller form.

So this is **not a re-skin** — the visual language is already live. The work is
**architectural**: turn the design system into named, documented React
components and recompose the screens to consume them, instead of the current
ad-hoc utility-class markup and duplicated bespoke widgets.

## Goal

Rebuild the frontend's **presentation layer** on top of the design system's
component primitives, while keeping the existing **logic layer** and all current
features. Net result: the same look, but the design system becomes the literal
foundation of the app's UI — fewer one-off implementations, a single `Banner`
instead of four, documented prop contracts, easier to extend.

## Decisions (from brainstorming)

1. **Intent:** build the new front end using the bundle.
2. **Scope:** rebuild the UI, keep the logic (`api/`, `context/`, `lib/`).
3. **Approach:** **A** — port the bundle's primitives into the app, then
   recompose screens onto them. (Not B "polish only", not C "rebuild mockups
   verbatim", which would regress features the mockups omit.)
4. **Testing:** **visual verification only** — no new test infra; verify each
   recomposed screen with before/after screenshots in the dev server. Existing
   `lib/*` tests stay green and untouched.
5. **Delivery:** **commit per verified phase directly on `main`** (explicitly
   chosen, overriding the default "branch first").

## Non-goals / hard constraints

- **Do not** change `api/`, `context/`, or `lib/` (or their tests). No data
  flow, routing, auth, or backend-contract changes.
- **Do not** hardcode the bundle's risk hexes into components. Risk band color,
  ramp, trend, and thresholds keep coming from `lib/risk.js` — the single source
  of truth tied to `backend/core/scoring.py` (25/50/75). The bundle's
  hardcoded `RISK_BANDS`/`RAMP` are reference only.
- **Preserve behavior exactly:** ARIA roles (`alert`/`status`/`dialog`),
  `:focus-visible` water outline, `prefers-reduced-motion` collapse, the mobile
  bottom-sheet (`<768px`) branch, lazy-loading of the detail panel/recharts,
  localStorage view persistence, and the sign-out cache-clear.
- **No visual regression.** Primitives are styled with the existing Tailwind
  tokens, not raw CSS variables. A screen looks identical before and after.

## Architecture

```
frontend/src/components/
  ui/                     # NEW — the design system as app-native components
    Button.jsx
    Card.jsx
    MicroLabel.jsx
    Badge.jsx
    Field.jsx
    Banner.jsx
    SegmentedControl.jsx  # relocated from components/
    RiskScoreCard.jsx     # relocated from components/
    TrendBadge.jsx        # extracted from RiskScoreCard
    RiskLegend.jsx        # relocated from components/MapLegend.jsx (kept export name MapLegend-compatible)
    index.js              # barrel re-export
```

- Each component mirrors the bundle's prop contract (its `.d.ts`) but is
  implemented with Tailwind classes consistent with the current codebase.
- The barrel lets consumers `import { Button, Card, Banner } from '../ui'`.
- Existing component files that move are replaced by their `ui/` version; all
  imports across the app are updated in the same phase.

## Component contracts

Primitives (new):

- **Button** — `variant: 'primary'|'secondary'|'ghost'` (default primary),
  `size: 'sm'|'md'` (default md), `fullWidth`, `href` (renders `<a>`),
  `disabled`, `type`, `onClick`, `children`. Maps onto the existing
  `.btn-primary`/`.btn-secondary` looks; `ghost` = quiet text button.
- **Card** — `padding` (number px | string, default 16), `as` (default `div`),
  plus the `.card` surface (border + shadow + radius).
- **MicroLabel** — `as` (default `p`); renders the `.microlabel` style.
- **Badge** — `tone: 'neutral'|'accent'|'low'|'medium'|'high'|'critical'`. Risk
  tones derive their color via `lib/risk.js`, not literals.
- **Field** — `id`, `label`, `type`, `value`, `onChange(value)`, `placeholder`,
  `hint`, `error`, `required`, `autoComplete`. Mono label + paper-bordered input
  + focus ring + error/hint line. Matches the current auth-form inputs.
- **Banner** — `tone: 'critical'|'warn'|'info'`, `icon`, `onDismiss`, `actions`,
  `children`. `role="alert"` for critical, else `role="status"`.

Domain components (relocate/keep behavior):

- **RiskScoreCard** — unchanged props (`risk`, `trend`, `month`, `label`); keeps
  reading `riskBand`/`trendInfo` from `lib/risk.js`. Trend pill extracted to
  `TrendBadge`.
- **TrendBadge** — `trend: 'worsening'|'stable'|'improving'` (+ whatever
  `lib/risk.js` `trendInfo` already supports). Used inside RiskScoreCard and
  standalone.
- **SegmentedControl** — unchanged props (`options`, `value`, `onChange`,
  `label`).
- **RiskLegend** — the current `MapLegend`, relocated; keeps
  `riskRampGradient`/`RISK_BANDS`/`NO_DATA_COLOR` from `lib/risk.js`.

## Recompose map (consumers)

| Current ad-hoc markup | Becomes |
|---|---|
| `MapPage` Brand / StatusCard / HardError | `Card` + `Button` + `MicroLabel` |
| `MapPage` inline `SessionExpiryNotice` | `Banner tone="warn"` |
| `AlertBanner` (critical) | `Banner tone="critical"` |
| `StaleDataBanner` (warn) | `Banner tone="warn"` |
| `WarmupBanner` (info/warn) | `Banner` |
| `DistrictPanel` header close button | `Button variant="ghost"` + `MicroLabel` |
| `DistrictDetails` "Plan with AI" / "See history" CTAs | `Button` (accent-tinted) |
| `panel/SectionTitle` eyebrows | `MicroLabel` |
| `auth/AuthForms` inputs | `Field` |
| advisor: `AdvisorPlanner` / `SiteProfileForm` / `ReportView` | `Card` / `Badge` (source tags, outlook, quick-win) / `Button` / `Field` |

Banners keep their existing data wiring (subscriptions, warmup ping, stale
state) — only the presentational shell is swapped to `Banner`.

## Phasing (each phase = verify + one commit on `main`)

0. **Primitives.** Create `ui/` with the six new primitives + barrel; relocate
   `RiskScoreCard`/`SegmentedControl`/`MapLegend→RiskLegend`; extract
   `TrendBadge`. Update imports repo-wide. Verify the app builds and the map
   screen renders unchanged. Commit.
1. **Banners → one `Banner`.** Recompose `AlertBanner`, `StaleDataBanner`,
   `WarmupBanner`, `SessionExpiryNotice`. Verify each banner state. Commit.
2. **MapPage chrome.** Brand, StatusCard, HardError onto `Card`/`Button`/
   `MicroLabel`. Verify. Commit.
3. **Detail panel + DistrictDetails.** Header, CTAs, section eyebrows. Verify
   district + cell panels (desktop dock + mobile sheet). Commit.
4. **Auth forms → `Field`.** Verify sign-in/up + error states. Commit.
5. **Advisor flow.** Goal picker, site form, report (allocation donut, priority
   actions, source tags) onto primitives. Verify the full flow. Commit.

Phases are independent enough to stop after any one with the app fully working.

## Verification approach (visual-only)

- Run the dev server on `:3000` (`npm run dev` in `frontend/`) via the preview
  tooling. The backend (`127.0.0.1:8000`) must be up for data-bearing screens;
  start it before phases that need populated panels. Chrome/banner/auth states
  can be verified without it.
- For each phase: screenshot the relevant screen/state **before** the recompose
  and **after**, at desktop (1280) and — for the panel — mobile (375). Confirm
  pixel-equivalence and check `preview_console_logs` for errors.
- Keep `npm test` (the `lib/*` Vitest suite) green throughout.

## Risks & mitigations

- **Import churn from relocating components** → do all moves + import updates in
  Phase 0 as one atomic commit; rely on the build to catch missed imports.
- **Subtle visual drift when translating inline-style bundle components to
  Tailwind** → the app already has Tailwind equivalents for most looks; diff
  against the existing utility classes, and screenshot-compare each phase.
- **Banner consolidation hiding a behavioral difference** (e.g. warmup retry,
  subscription state) → keep all data/handlers in the consumer; `Banner` is
  presentational only.

## Out of scope

- New surfaces not already in the app (the bundle's "next screens" all already
  exist).
- Any change to tokens, backend, or the risk-band contract.
- Adding component-test infrastructure (explicitly deferred — visual only).
