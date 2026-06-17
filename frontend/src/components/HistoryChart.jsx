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
import { historyTickInterval } from '../lib/chart.js';
import {
  CRITICAL_THRESHOLD,
  HIGH_THRESHOLD,
  formatMonth,
  riskBand,
  shortMonth,
} from '../lib/risk.js';
import { ChartSkeleton } from './Skeletons.jsx';

export default function HistoryChart({ points, isLoading }) {
  if (isLoading) return <ChartSkeleton height={300} />;
  if (!points?.length) {
    return (
      <p className="rounded-lg border border-dashed border-ink/20 p-4 text-sm text-ink-soft">
        No historical risk scores for this location yet.
      </p>
    );
  }

  const data = points.map((point) => ({
    month: point.month,
    label: shortMonth(point.month),
    risk: point.risk,
  }));

  return (
    <figure aria-label={`Observed risk history, ${data.length} months`}>
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
            dot={false}
            activeDot={{ r: 4, fill: '#1C2B33', strokeWidth: 0 }}
            isAnimationActive={false}
            name="Observed risk"
          />
        </LineChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 text-[11px] text-ink-soft">
        Observed monthly risk over the last {data.length} months. Dashed lines mark the
        High and Critical thresholds.
      </figcaption>
    </figure>
  );
}

function HistoryTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
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
