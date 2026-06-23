// 6-month forecast: predicted risk line over the model's 10th–90th percentile
// ensemble band, with the High/Critical thresholds as fixed reference lines.
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CRITICAL_THRESHOLD, HIGH_THRESHOLD, shortMonth } from '../lib/risk.js';
import { CHART } from '../lib/reportManifest.js';
import { ChartSkeleton } from './Skeletons.jsx';

export default function ForecastChart({ points, isLoading }) {
  if (isLoading) return <ChartSkeleton />;
  if (!points?.length) {
    return (
      <p className="rounded-lg border border-dashed border-ink/20 p-4 text-sm text-ink-soft">
        No forecast available for this location yet.
      </p>
    );
  }

  const data = points.map((point) => ({
    month: shortMonth(point.month),
    predicted: point.predicted_risk,
    band: [point.confidence_interval_low, point.confidence_interval_high],
  }));

  return (
    <figure aria-label="6-month risk forecast chart with confidence interval">
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -22 }}>
          <XAxis
            dataKey="month"
            // Force every month to label. Recharts defaults to interval="preserveEnd",
            // which keeps the last tick and drops the colliding second-to-last one —
            // in a 6-month window that silently hides the 5th month's label.
            interval={0}
            tick={{ fontSize: 11, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            tickLine={false}
            axisLine={{ stroke: CHART.axis }}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={{ fontSize: 11, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ForecastTooltip />} />
          <ReferenceLine
            y={HIGH_THRESHOLD}
            stroke={CHART.risk.high}
            strokeDasharray="5 4"
            label={{ value: 'High', position: 'insideTopRight', fontSize: 10, fill: '#8C2A0D' }}
          />
          <ReferenceLine
            y={CRITICAL_THRESHOLD}
            stroke={CHART.risk.critical}
            strokeDasharray="5 4"
            label={{ value: 'Critical', position: 'insideTopRight', fontSize: 10, fill: CHART.risk.critical }}
          />
          <Area
            dataKey="band"
            stroke="none"
            fill={CHART.water}
            fillOpacity={0.14}
            isAnimationActive={false}
            name="Likely range"
          />
          <Line
            dataKey="predicted"
            stroke={CHART.water}
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: CHART.water, strokeWidth: 0 }}
            isAnimationActive={false}
            name="Predicted risk"
          />
        </ComposedChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 text-[11px] text-ink-soft">
        Shaded area = likely range (model confidence). Dashed lines mark the High and
        Critical thresholds.
      </figcaption>
    </figure>
  );
}

function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-mono font-semibold">{label}</p>
      <p className="mt-1">
        Predicted: <strong className="font-mono">{row.predicted.toFixed(1)}</strong>
      </p>
      <p className="text-ink-soft">
        Range {row.band[0].toFixed(1)} – {row.band[1].toFixed(1)}
      </p>
    </div>
  );
}
