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
