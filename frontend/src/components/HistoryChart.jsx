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
  earliestMonth,
  historyTickInterval,
  historyWindow,
  latestMonth,
  monthsBetween,
} from '../lib/chart.js';
import {
  CRITICAL_THRESHOLD,
  HIGH_THRESHOLD,
  formatMonth,
  riskBand,
  shortMonth,
} from '../lib/risk.js';
import { ChartSkeleton } from './Skeletons.jsx';

// Above this many actual observations the dots crowd the line, so we drop them
// and let the line carry the shape; at or below it (a few years or a lone
// month) the dots aid reading and keep an isolated point from vanishing.
const MAX_MONTHS_WITH_DOTS = 36;

export default function HistoryChart({ points, isLoading }) {
  if (isLoading) return <ChartSkeleton height={300} />;
  if (!points?.length) {
    return (
      <p className="rounded-lg border border-dashed border-ink/20 p-4 text-sm text-ink-soft">
        No historical risk scores for this location yet.
      </p>
    );
  }

  // Span the full available record: from the earliest scored month through the
  // latest, inclusive. Left-join the observations onto that continuous window so
  // unscored months (e.g. the 2017-18 GRACE satellite gap) render as breaks in
  // the line rather than being silently collapsed.
  const lastDataMonth = latestMonth(points) ?? currentMonthKey();
  const firstDataMonth = earliestMonth(points) ?? lastDataMonth;
  const span = monthsBetween(firstDataMonth, lastDataMonth);
  const data = historyWindow(points, lastDataMonth, span).map((slot) => ({
    month: slot.month,
    label: shortMonth(slot.month),
    risk: slot.risk,
  }));
  const firstMonth = data[0]?.month;
  const lastMonth = data[data.length - 1]?.month;
  const showDots = data.filter((slot) => slot.risk != null).length <= MAX_MONTHS_WITH_DOTS;

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
            // no line segment) is still visible instead of vanishing — but only
            // for shorter spans, where they don't crowd the line.
            dot={showDots ? { r: 2, fill: '#1C2B33', strokeWidth: 0 } : false}
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
