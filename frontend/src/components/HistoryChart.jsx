// Full 2-year observed-risk history: the same data behind the panel's compact
// sparkline, rendered as a proper chart with axes, the High/Critical threshold
// reference lines (matching ForecastChart), and a per-month tooltip.
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  currentMonthKey,
  historyTickInterval,
  historyWindow,
  latestMonth,
} from '../lib/chart.js';
import {
  CRITICAL_THRESHOLD,
  HIGH_THRESHOLD,
  formatMonth,
  riskBand,
  shortMonth,
} from '../lib/risk.js';
import { ChartSkeleton } from './Skeletons.jsx';

// The window spans two years — 24 monthly slots — ending at the anchor month:
// 23 months back plus the anchor month, inclusive. Matching the API's
// EXPORT_HISTORY_MONTHS (24) window means the line fills the axis edge to edge
// instead of leaving a stray empty slot.
const HISTORY_MONTHS_BACK = 23;

export default function HistoryChart({ points, isLoading }) {
  if (isLoading) return <ChartSkeleton height={300} />;
  if (!points?.length) {
    return (
      <p className="rounded-lg border border-dashed border-ink/20 p-4 text-sm text-ink-soft">
        No historical risk scores for this location yet.
      </p>
    );
  }

  // Anchor the 2-year window to the latest *scored* month (observed data lags
  // the calendar, so the wall clock would push the series out of view); fall
  // back to the current month only when there's no data at all. Left-join the
  // observations onto the fixed window so unscored months render as gaps rather
  // than shrinking the axis to wherever the data happens to fall.
  const anchorMonth = latestMonth(points) ?? currentMonthKey();
  const data = historyWindow(points, anchorMonth, HISTORY_MONTHS_BACK).map((slot) => ({
    month: slot.month,
    label: shortMonth(slot.month),
    risk: slot.risk,
  }));
  const firstMonth = data[0]?.month;
  const lastMonth = data[data.length - 1]?.month;

  return (
    <figure
      aria-label={`Observed risk history from ${formatMonth(firstMonth)} to ${formatMonth(lastMonth)}`}
    >
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 10, bottom: 0, left: -22 }}>
          <XAxis
            dataKey="label"
            // Thin the labels so a 24-month axis stays readable instead of a
            // wall of overlapping ticks.
            interval={historyTickInterval(data.length)}
            tick={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', fill: '#51626C' }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(28,43,51,0.18)' }}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={{ fontSize: 11, fontFamily: '"IBM Plex Mono", monospace', fill: '#51626C' }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<HistoryTooltip />} />
          <ReferenceLine
            y={HIGH_THRESHOLD}
            stroke="#FF5722"
            strokeDasharray="5 4"
            label={{ value: 'High', position: 'insideTopRight', fontSize: 10, fill: '#8C2A0D' }}
          />
          <ReferenceLine
            y={CRITICAL_THRESHOLD}
            stroke="#B71C1C"
            strokeDasharray="5 4"
            label={{ value: 'Critical', position: 'insideTopRight', fontSize: 10, fill: '#B71C1C' }}
          />
          <Line
            dataKey="risk"
            // Observed history reads as ink, mirroring the sparkline — the teal
            // line elsewhere always means *forecast*.
            stroke="#1C2B33"
            strokeWidth={2}
            // Leave unscored months as gaps rather than drawing a straight line
            // across them — a bridged line would imply data we don't have.
            connectNulls={false}
            // Small dots so a single isolated month (a gap on both sides draws
            // no line segment) is still visible instead of vanishing.
            dot={{ r: 2, fill: '#1C2B33', strokeWidth: 0 }}
            activeDot={{ r: 4, fill: '#1C2B33', strokeWidth: 0 }}
            isAnimationActive={false}
            name="Observed risk"
          />
        </LineChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 text-[11px] text-ink-soft">
        Observed monthly risk, {formatMonth(firstMonth)} – {formatMonth(lastMonth)}. Any gaps
        mark unscored months; dashed lines mark the High and Critical thresholds.
      </figcaption>
    </figure>
  );
}

function HistoryTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  if (row.risk == null) {
    return (
      <div className="card px-3 py-2 text-xs">
        <p className="font-mono font-semibold">{formatMonth(row.month)}</p>
        <p className="mt-1 text-ink-soft">No observation yet</p>
      </div>
    );
  }
  const band = riskBand(row.risk);
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-mono font-semibold">{formatMonth(row.month)}</p>
      <p className="mt-1">
        Risk: <strong className="font-mono">{row.risk.toFixed(1)}</strong>
      </p>
      <p className="text-ink-soft" style={{ color: band.level === 'medium' ? '#7A5800' : band.color }}>
        {band.label}
      </p>
    </div>
  );
}
