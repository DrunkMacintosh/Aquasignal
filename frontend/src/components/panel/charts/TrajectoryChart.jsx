// Grounded: the district's observed risk history flowing into the 6-month
// forecast, with the model's confidence band and the High/Critical thresholds.
// Both series come from the snapshot the panel already loaded — no AI numbers.
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
import { CRITICAL_THRESHOLD, HIGH_THRESHOLD, formatMonth, shortMonth } from '../../../lib/risk.js';
import { CHART } from '../../../lib/reportManifest.js';

export default function TrajectoryChart({ history = [], forecast = [] }) {
  const past = (history ?? []).map((p) => ({
    month: p.month,
    label: shortMonth(p.month),
    observed: p.risk,
  }));
  const future = (forecast ?? []).map((p) => ({
    month: p.month,
    label: shortMonth(p.month),
    predicted: p.predicted_risk,
    band: [p.confidence_interval_low, p.confidence_interval_high],
  }));

  // Bridge the two lines: seed the forecast line at the last observed point so
  // the teal line continues from the ink line instead of floating detached.
  if (past.length && future.length) {
    const last = past[past.length - 1];
    last.predicted = last.observed;
    last.band = [last.observed, last.observed];
  }
  const data = [...past, ...future];
  if (!data.length) return null;

  const splitLabel = future.length ? future[0].label : null;

  return (
    <figure aria-label="Observed risk history and 6-month forecast">
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data} margin={{ top: 8, right: 10, bottom: 0, left: -22 }}>
          <XAxis
            dataKey="label"
            interval="preserveStartEnd"
            minTickGap={24}
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
          <Tooltip content={<TrajectoryTooltip />} />
          <ReferenceLine y={HIGH_THRESHOLD} stroke={CHART.risk.high} strokeDasharray="5 4"
            label={{ value: 'High', position: 'insideTopRight', fontSize: 10, fill: '#8C2A0D' }} />
          <ReferenceLine y={CRITICAL_THRESHOLD} stroke={CHART.risk.critical} strokeDasharray="5 4"
            label={{ value: 'Critical', position: 'insideTopRight', fontSize: 10, fill: CHART.risk.critical }} />
          {splitLabel && (
            <ReferenceLine x={splitLabel} stroke={CHART.inkFaint} strokeDasharray="2 4"
              label={{ value: 'forecast →', position: 'insideTopLeft', fontSize: 9, fill: CHART.inkFaint }} />
          )}
          <Area dataKey="band" stroke="none" fill={CHART.water} fillOpacity={0.13}
            isAnimationActive={false} name="Likely range" connectNulls />
          <Line dataKey="observed" stroke={CHART.ink} strokeWidth={2} dot={false}
            connectNulls={false} isAnimationActive={false} name="Observed" />
          <Line dataKey="predicted" stroke={CHART.water} strokeWidth={2.5} strokeDasharray="4 3"
            dot={{ r: 3, fill: CHART.water, strokeWidth: 0 }} connectNulls
            isAnimationActive={false} name="Forecast" />
        </ComposedChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 text-[11px] text-ink-soft">
        Ink line = observed risk; dashed teal = forecast with its likely range. Dashed
        horizontals mark the High and Critical thresholds.
      </figcaption>
    </figure>
  );
}

function TrajectoryTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const value = row.observed ?? row.predicted;
  if (value == null) return null;
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-mono font-semibold">{formatMonth(row.month)}</p>
      <p className="mt-1">
        {row.observed != null ? 'Observed' : 'Forecast'}:{' '}
        <strong className="font-mono">{value.toFixed(1)}</strong>
      </p>
      {row.observed == null && row.band && (
        <p className="text-ink-soft">Range {row.band[0].toFixed(1)} – {row.band[1].toFixed(1)}</p>
      )}
    </div>
  );
}
