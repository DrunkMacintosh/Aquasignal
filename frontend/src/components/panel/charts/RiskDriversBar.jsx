// AI estimate: the advisor's weighting of the factors driving well-failure risk
// at this location, as a ranked horizontal bar chart. Weights are relative
// (0-100 by contribution), so the chart reads as "what matters most here".
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CHART } from '../../../lib/reportManifest.js';

export default function RiskDriversBar({ drivers = [], animate = false }) {
  const data = (drivers ?? [])
    .filter((d) => d.label && Number(d.weight) > 0)
    .map((d) => ({ label: d.label, weight: Number(d.weight), note: d.note ?? '' }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 6);
  if (!data.length) return null;

  // Height scales with the number of bars so labels never crowd.
  const height = data.length * 38 + 16;

  return (
    <figure aria-label="Factors driving risk, ranked by contribution">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, bottom: 0, left: 0 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis
            type="category"
            dataKey="label"
            width={130}
            tick={{ fontSize: 11, fill: CHART.ink }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<DriverTooltip />} cursor={{ fill: 'rgba(11,31,51,0.05)' }} />
          <Bar dataKey="weight" radius={[0, 4, 4, 0]} isAnimationActive={animate} barSize={16}>
            {data.map((row, i) => (
              <Cell key={row.label} fill={CHART.categorical[i % CHART.categorical.length]} />
            ))}
            <LabelList
              dataKey="weight"
              position="right"
              formatter={(v) => `${Math.round(v)}`}
              style={{ fontSize: 11, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

function DriverTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-semibold">{row.label}</p>
      <p className="mt-0.5 font-mono">contribution {Math.round(row.weight)}/100</p>
      {row.note && <p className="mt-1 max-w-[12rem] text-ink-soft">{row.note}</p>}
    </div>
  );
}
