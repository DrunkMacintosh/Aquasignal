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
