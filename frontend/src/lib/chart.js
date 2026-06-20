// Small chart helpers shared across recharts views.

/**
 * Recharts XAxis `interval` for a time series of `count` points, targeting at
 * most `maxLabels` axis labels so a long (e.g. 24-month) history doesn't render
 * colliding, unreadable tick labels.
 *
 * recharts `interval` is the number of ticks to SKIP between two labels, so 0
 * labels every point. We pick the smallest skip that keeps the label count at
 * or below `maxLabels`.
 *
 * @param {number} count - number of data points on the axis
 * @param {number} [maxLabels=8] - upper bound on visible axis labels
 * @returns {number} the recharts `interval` value (>= 0)
 */
export function historyTickInterval(count, maxLabels = 8) {
  if (!Number.isFinite(count) || count <= maxLabels) return 0;
  return Math.ceil(count / maxLabels) - 1;
}

/** Current calendar month as a 'YYYY-MM' key (local time). */
export function currentMonthKey(now = new Date()) {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

/**
 * The most recent 'YYYY-MM' present in `points`, or null when there are none.
 * 'YYYY-MM' sorts lexicographically the same as chronologically, so a plain
 * string max is correct. Used to anchor the history window to the latest
 * *scored* month rather than the wall clock — observed data lags the calendar
 * by months, so anchoring to "now" would push the whole series out of view.
 */
export function latestMonth(points) {
  if (!points?.length) return null;
  return points.reduce((max, p) => (p.month > max ? p.month : max), points[0].month);
}

/** The earliest 'YYYY-MM' present in `points`, or null when there are none. */
export function earliestMonth(points) {
  if (!points?.length) return null;
  return points.reduce((min, p) => (p.month < min ? p.month : min), points[0].month);
}

/**
 * Whole months from `startMonth` to `endMonth` (both 'YYYY-MM'); 0 when equal,
 * negative if start is after end. Used to size the history window to the full
 * span of available data.
 */
export function monthsBetween(startMonth, endMonth) {
  const [sy, sm] = String(startMonth ?? '').split('-').map(Number);
  const [ey, em] = String(endMonth ?? '').split('-').map(Number);
  if (!sy || !sm || !ey || !em) return 0;
  return (ey - sy) * 12 + (em - sm);
}

/**
 * Ascending list of 'YYYY-MM' keys for a continuous window ending at `endMonth`
 * and reaching `monthsBack` months before it — `monthsBack + 1` entries,
 * inclusive of both ends. Year rollover is handled by Date's index normalising.
 *
 * @param {string} endMonth - last month in the window, 'YYYY-MM'
 * @param {number} monthsBack - how many months before endMonth to start
 * @returns {string[]}
 */
export function monthSequence(endMonth, monthsBack) {
  const [year, month] = String(endMonth ?? '').split('-').map(Number);
  if (!year || !month) return [];
  const out = [];
  for (let i = monthsBack; i >= 0; i--) {
    const d = new Date(year, month - 1 - i, 1); // month is 1-based; Date normalises
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }
  return out;
}

/**
 * Left-join observed history `points` onto the fixed window running from
 * `monthsBack` months before `endMonth` through `endMonth` (inclusive). Every
 * slot is present so a chart spans the whole window regardless of which months
 * were actually scored; months without an observation get `risk: null`, which
 * recharts renders as a gap.
 *
 * @param {Array<{month: string, risk: number}>} [points]
 * @param {string} endMonth - 'YYYY-MM'
 * @param {number} monthsBack
 * @returns {Array<{month: string, risk: number|null}>}
 */
export function historyWindow(points, endMonth, monthsBack) {
  const byMonth = new Map((points ?? []).map((p) => [p.month, p]));
  return monthSequence(endMonth, monthsBack).map((month) => ({
    month,
    risk: byMonth.has(month) ? byMonth.get(month).risk : null,
  }));
}
