// Grounded: recent precipitation vs. evapotranspiration (mm) from the snapshot's
// satellite observations. When ET outpaces rainfall the surplus available to
// recharge the aquifer shrinks — this is the pressure behind the risk score.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatMonth, shortMonth } from '../../../lib/risk.js';
import { CHART } from '../../../lib/reportManifest.js';

export default function WaterBalanceChart({ satellite = [] }) {
  const data = (satellite ?? [])
    .filter((m) => m.precipitation != null || m.evapotranspiration != null)
    .map((m) => ({
      month: m.month,
      label: shortMonth(m.month),
      precip: m.precipitation ?? 0,
      et: m.evapotranspiration ?? 0,
    }));
  if (!data.length) return null;

  return (
    <figure aria-label="Precipitation versus evapotranspiration">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barGap={2}>
          <CartesianGrid vertical={false} stroke={CHART.grid} />
          <XAxis
            dataKey="label"
            interval={0}
            tick={{ fontSize: 11, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            tickLine={false}
            axisLine={{ stroke: CHART.axis }}
          />
          <YAxis
            tick={{ fontSize: 11, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            tickLine={false}
            axisLine={false}
            width={44}
            label={{ value: 'mm', angle: -90, position: 'insideLeft', fontSize: 10, fill: CHART.inkFaint }}
          />
          <Tooltip content={<BalanceTooltip />} cursor={{ fill: 'rgba(28,43,51,0.04)' }} />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: CHART.mono }} />
          <Bar dataKey="precip" name="Precipitation" fill={CHART.water} radius={[2, 2, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="et" name="Evapotranspiration" fill="#E0A93B" radius={[2, 2, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 text-[11px] text-ink-soft">
        Months where the ochre bar (loss) approaches or exceeds the teal bar (rainfall) leave
        little surplus to recharge the aquifer.
      </figcaption>
    </figure>
  );
}

function BalanceTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const net = row.precip - row.et;
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-mono font-semibold">{formatMonth(row.month)}</p>
      <p className="mt-1">Rain: <strong className="font-mono">{row.precip.toFixed(0)}</strong> mm</p>
      <p>Loss: <strong className="font-mono">{row.et.toFixed(0)}</strong> mm</p>
      <p className="text-ink-soft" style={{ color: net >= 0 ? CHART.risk.low : CHART.risk.high }}>
        Surplus {net >= 0 ? '+' : ''}{net.toFixed(0)} mm
      </p>
    </div>
  );
}
