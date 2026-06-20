// Per-need report manifest (Option C: adaptive per-need report). Each need lists
// the chart sections to render, in order, with topic-specific titles/captions.
// The JSON schema the model fills is identical across needs (see core/advisor.py
// NEED_BLUEPRINT) — only the framing here changes, so each report reads bespoke
// to the usage topic while the data contract stays stable.
//
// Section `key` selects which chart component ReportView renders; `source` says
// whether it is grounded in real snapshot data or an AI-derived estimate (the
// latter gets an "AI estimate" tag so users never mistake guidance for a
// measurement). Keys must match the switch in ReportView.jsx.

// Brand-aligned chart tokens (mirror tailwind.config.js — recharts needs raw
// hex, not CSS classes).
export const CHART = {
  ink: '#1C2B33',
  inkSoft: '#51626C',
  inkFaint: '#8B98A0',
  water: '#0E6E83',
  waterDeep: '#0A4F5E',
  waterWash: '#E3EEF0',
  paper: '#F4F1E9',
  surface: '#FDFCF7',
  grid: 'rgba(28,43,51,0.10)',
  axis: 'rgba(28,43,51,0.18)',
  mono: '"IBM Plex Mono", monospace',
  risk: { low: '#4CAF50', medium: '#FFC107', high: '#FF5722', critical: '#B71C1C' },
  // Categorical ramp for donut slices / driver bars — distinct hues that still
  // sit in the warm "survey ledger" world rather than clashing primaries.
  categorical: [
    '#0E6E83', // water
    '#3E9A8F', // teal-green
    '#7BB36F', // sage
    '#E0A93B', // ochre
    '#C8612E', // terracotta
    '#9B3B4E', // wine
    '#5E548E', // muted violet
    '#8B98A0', // slate (overflow)
  ],
};

// Sections shared by every need (universal narrative scaffolding renders around
// these in ReportView). Order + titles are overridden per need below.
const SECTION = {
  trajectory: {
    key: 'trajectory',
    source: 'grounded',
    title: 'Risk trajectory',
    caption: 'Observed well-failure risk and the 6-month forecast for this district.',
  },
  kpis: { key: 'kpis', source: 'ai', title: 'Key targets' },
  allocation: { key: 'allocation', source: 'ai', title: 'Recommended water budget' },
  waterBalance: {
    key: 'waterBalance',
    source: 'grounded',
    title: 'Water balance',
    caption: 'Recent precipitation vs. evapotranspiration — the pressure on recharge.',
  },
  recharge: {
    key: 'recharge',
    source: 'grounded',
    title: 'Aquifer recharge capacity',
    caption: 'Soil permeability and relative recharge potential for this district.',
  },
  drivers: { key: 'drivers', source: 'ai', title: 'What is driving risk here' },
  priorityActions: { key: 'priorityActions', source: 'ai', title: 'Priority actions' },
};

/** Compose a per-need section list, overriding titles where the topic differs. */
function sections(order, overrides = {}) {
  return order.map((key) => ({ ...SECTION[key], ...(overrides[key] ?? {}) }));
}

export const REPORT_MANIFEST = {
  water_sustainability: {
    label: 'Water sustainability plan',
    lede: 'A plan to keep abstraction within what the aquifer can replenish.',
    sections: sections(
      ['trajectory', 'kpis', 'recharge', 'allocation', 'waterBalance', 'drivers', 'priorityActions'],
      {
        kpis: { title: 'Sustainability targets' },
        allocation: { title: 'Recommended abstraction budget' },
      },
    ),
  },
  agriculture: {
    label: 'Irrigation & agriculture plan',
    lede: 'A plan to water crops reliably without drawing the wells down.',
    sections: sections(
      ['trajectory', 'kpis', 'allocation', 'waterBalance', 'recharge', 'drivers', 'priorityActions'],
      {
        kpis: { title: 'Irrigation targets' },
        allocation: { title: 'Recommended irrigation budget' },
        waterBalance: {
          title: 'Seasonal water balance',
          caption: 'Rainfall vs. crop water loss — when irrigation demand peaks.',
        },
      },
    ),
  },
  urban_supply: {
    label: 'Urban & domestic supply plan',
    lede: 'A plan to meet household and municipal demand with resilient supply.',
    sections: sections(
      ['trajectory', 'kpis', 'allocation', 'drivers', 'recharge', 'waterBalance', 'priorityActions'],
      {
        kpis: { title: 'Supply targets' },
        allocation: { title: 'Recommended supply allocation' },
        drivers: { title: 'What is straining supply here' },
      },
    ),
  },
  industrial: {
    label: 'Industrial water plan',
    lede: 'A plan to run processes sustainably with reuse and abstraction limits.',
    sections: sections(
      ['trajectory', 'kpis', 'allocation', 'drivers', 'recharge', 'waterBalance', 'priorityActions'],
      {
        kpis: { title: 'Process & reuse targets' },
        allocation: { title: 'Recommended process-water budget' },
      },
    ),
  },
};

/** Manifest for a need, falling back to the sustainability layout if unknown. */
export function manifestForNeed(need) {
  return REPORT_MANIFEST[need] ?? REPORT_MANIFEST.water_sustainability;
}

/**
 * Normalize allocation slices so they sum to ~100 for the donut. A free model
 * rarely returns a clean 100; we render proportions, not the raw numbers. Drops
 * non-positive slices. Returns [] when there is nothing to show.
 */
export function normalizeAllocation(slices = []) {
  const positive = (slices ?? []).filter((s) => Number(s?.percent) > 0);
  const total = positive.reduce((sum, s) => sum + Number(s.percent), 0);
  if (total <= 0) return [];
  return positive.map((s) => ({
    label: s.label,
    note: s.note ?? '',
    percent: (Number(s.percent) / total) * 100,
  }));
}
