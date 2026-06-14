// Risk banding and trend rules. Thresholds and labels mirror
// backend/core/scoring.py — change them there first, then here.

export const CRITICAL_THRESHOLD = 75;
export const HIGH_THRESHOLD = 50;
export const TREND_DELTA_POINTS = 5;
export const TREND_WINDOW_MONTHS = 3;

// Fill for districts whose cells have no current score (ocean-masked etc.).
export const NO_DATA_COLOR = '#D8D4C8';

export const RISK_BANDS = [
  { level: 'low', label: 'Low', min: 0, max: 25, color: '#4CAF50', onColor: '#103412' },
  { level: 'medium', label: 'Medium', min: 25, max: 50, color: '#FFC107', onColor: '#4a3800' },
  { level: 'high', label: 'High', min: 50, max: 75, color: '#FF5722', onColor: '#ffffff' },
  { level: 'critical', label: 'Critical', min: 75, max: 100, color: '#B71C1C', onColor: '#ffffff' },
];

export function riskBand(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return RISK_BANDS[0];
  const clamped = Math.min(Math.max(value, 0), 100);
  return RISK_BANDS.findLast((band) => clamped >= band.min) ?? RISK_BANDS[0];
}

// Continuous colour ramp for the map choropleth. A `step` fill paints every
// district in a band the same flat colour; this ramp interpolates between stops
// so each score reads as its own shade. The boundary stops (0/25/50/75) are
// pinned to RISK_BANDS so the legend swatches and band chips stay truthful.
//
// The top half is deliberately dense: in Vietnam almost every district sits in
// the 60-100 range, so a plain orange->dark-red ramp leaves them near-identical
// (our eyes barely separate dark reds). Above 75 the ramp shifts HUE through
// crimson -> magenta -> violet -> near-black, which gives high-but-different
// scores obvious contrast and follows the "beyond maximum" convention (AQI
// hazardous, extreme-heat scales). Colour stays absolute — a shade always means
// the same score, no data-dependent rescaling.
export const RISK_RAMP = [
  { stop: 0, color: RISK_BANDS[0].color }, // low
  { stop: 12.5, color: '#9CCC3C' },
  { stop: 25, color: RISK_BANDS[1].color }, // medium
  { stop: 37.5, color: '#FF9800' },
  { stop: 50, color: RISK_BANDS[2].color }, // high — vivid orange
  { stop: 56, color: '#F73E1B' },
  { stop: 62, color: '#E5231D' },
  { stop: 68, color: '#D11423' },
  { stop: 75, color: RISK_BANDS[3].color }, // critical — deep red
  { stop: 81, color: '#9B0E4E' }, // wine, shifting toward magenta
  { stop: 86, color: '#7B1FA2' }, // violet
  { stop: 91, color: '#5E16A0' }, // deep violet
  { stop: 96, color: '#3B0D6E' }, // indigo
  { stop: 100, color: '#1A0533' }, // near-black violet — most extreme
];

/** CSS `linear-gradient(...)` mirroring RISK_RAMP, for the legend ramp bar. */
export function riskRampGradient(direction = 'to right') {
  const stops = RISK_RAMP.map(({ stop, color }) => `${color} ${stop}%`).join(', ');
  return `linear-gradient(${direction}, ${stops})`;
}

/**
 * MapLibre `fill-color` expression: RISK_RAMP across the absolute 0-100 score
 * domain. Colour is absolute — a shade always means the same score, with no
 * data-dependent rescaling. Districts with no score (current_risk null) branch
 * to the "no data" grey before the interpolation.
 */
export function fillColorExpression() {
  const stops = RISK_RAMP.flatMap(({ stop, color }) => [stop, color]);
  return [
    'case',
    ['==', ['coalesce', ['get', 'current_risk'], -1], -1],
    NO_DATA_COLOR,
    ['interpolate', ['linear'], ['get', 'current_risk'], ...stops],
  ];
}

export const TRENDS = {
  worsening: { arrow: '↑', label: 'Worsening', tone: 'bad' },
  stable: { arrow: '→', label: 'Stable', tone: 'neutral' },
  improving: { arrow: '↓', label: 'Improving', tone: 'good' },
};

export function trendInfo(trend) {
  return TRENDS[trend] ?? TRENDS.stable;
}

/** Same ±5-points-over-3-months rule the backend applies per cell. */
export function trendFromHistory(monthly) {
  if (!Array.isArray(monthly) || monthly.length < TREND_WINDOW_MONTHS + 1) return 'stable';
  const latest = monthly[monthly.length - 1].risk;
  const prior = monthly[monthly.length - 1 - TREND_WINDOW_MONTHS].risk;
  const delta = latest - prior;
  if (delta >= TREND_DELTA_POINTS) return 'worsening';
  if (delta <= -TREND_DELTA_POINTS) return 'improving';
  return 'stable';
}

/** '10.125_105.625' -> '10.125°N · 105.625°E' */
export function formatCellName(cellId) {
  const [latRaw, lonRaw] = String(cellId ?? '').split('_');
  const lat = Number(latRaw);
  const lon = Number(lonRaw);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return String(cellId ?? 'Unknown cell');
  const latLabel = `${Math.abs(lat).toFixed(3)}°${lat < 0 ? 'S' : 'N'}`;
  const lonLabel = `${Math.abs(lon).toFixed(3)}°${lon < 0 ? 'W' : 'E'}`;
  return `${latLabel} · ${lonLabel}`;
}

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** '2026-05' -> 'May 2026' */
export function formatMonth(yearMonth) {
  const [year, month] = String(yearMonth ?? '').split('-').map(Number);
  if (!year || !month || month < 1 || month > 12) return String(yearMonth ?? '');
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

/** '2026-05' -> 'May 26' (chart axis labels) */
export function shortMonth(yearMonth) {
  const [year, month] = String(yearMonth ?? '').split('-').map(Number);
  if (!year || !month || month < 1 || month > 12) return String(yearMonth ?? '');
  return `${MONTH_NAMES[month - 1]} ${String(year).slice(2)}`;
}
