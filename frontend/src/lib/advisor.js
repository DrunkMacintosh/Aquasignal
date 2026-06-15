// AI advisor helpers: the selectable planning needs and a reducer that turns
// the panel's already-loaded React Query data into the compact snapshot the
// backend injects into the model's system prompt (Option A thin proxy).
import { trendFromHistory } from './risk.js';

// `id` values MUST match the backend AdvisorNeed Literal (schemas.py) and the
// NEED_GUIDANCE map (core/advisor.py); advisor.test.js pins them.
export const ADVISOR_NEEDS = [
  {
    id: 'water_sustainability',
    label: 'Water sustainability',
    blurb: 'Long-term aquifer conservation',
  },
  {
    id: 'agriculture',
    label: 'Agriculture & irrigation',
    blurb: 'Crop & irrigation planning',
  },
  {
    id: 'urban_supply',
    label: 'Urban / domestic supply',
    blurb: 'Household & municipal demand',
  },
  {
    id: 'industrial',
    label: 'Industrial use',
    blurb: 'Process water & reuse',
  },
];

// Keep the prompt context (and free-tier token cost) bounded: the recent
// observed trend and the latest satellite snapshot carry the signal.
const HISTORY_MONTHS = 12;
const SATELLITE_MONTHS = 6;

/** Label for a need id, or the id itself if unknown. */
export function needLabel(needId) {
  return ADVISOR_NEEDS.find((need) => need.id === needId)?.label ?? needId;
}

/**
 * Reduce the district's cached datasets to the backend AdvisorSnapshot shape.
 * Every field is null/empty-safe so a partially loaded panel still produces a
 * valid snapshot.
 *
 * @param {{
 *   monthly?: Array<{month: string, risk: number, risk_level: string}>,
 *   forecast?: Array<object>,
 *   satellite?: Array<object>,
 *   permeability?: object | null,
 * }} data
 */
export function buildSnapshot({
  monthly = [],
  forecast = [],
  satellite = [],
  permeability = null,
} = {}) {
  const history = monthly ?? [];
  const latest = history[history.length - 1] ?? null;

  return {
    current_risk: latest?.risk ?? null,
    risk_level: latest?.risk_level ?? null,
    trend: trendFromHistory(history),
    latest_month: latest?.month ?? null,
    history: history.slice(-HISTORY_MONTHS).map((point) => ({
      month: point.month,
      risk: point.risk,
      risk_level: point.risk_level,
    })),
    forecast: (forecast ?? []).map((point) => ({
      month: point.month,
      predicted_risk: point.predicted_risk,
      confidence_interval_low: point.confidence_interval_low,
      confidence_interval_high: point.confidence_interval_high,
    })),
    satellite: (satellite ?? []).slice(-SATELLITE_MONTHS),
    permeability_index: permeability?.permeability_index ?? null,
    permeability_class: permeability?.permeability_class ?? null,
    recharge_value: permeability?.recharge_value ?? null,
    recharge_label: permeability?.recharge_label ?? null,
    net_infiltration_mm: permeability?.net_infiltration_mm ?? null,
  };
}
