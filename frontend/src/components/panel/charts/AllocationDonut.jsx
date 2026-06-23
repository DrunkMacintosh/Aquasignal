// AI estimate: the advisor's recommended split of total water use across the
// need's categories, drawn as a donut. Percentages are normalized to 100
// client-side (a free model rarely returns a clean total) — we render the
// proportions, not the raw numbers.
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { CHART, normalizeAllocation } from '../../../lib/reportManifest.js';

export default function AllocationDonut({ allocation = [], animate = false }) {
  const slices = normalizeAllocation(allocation);
  if (!slices.length) return null;

  const data = slices.map((s, i) => ({
    ...s,
    color: CHART.categorical[i % CHART.categorical.length],
  }));

  return (
    <figure
      className="flex flex-col items-center gap-3 sm:flex-row sm:gap-4"
      aria-label="Recommended water budget allocation"
    >
      <div className="h-40 w-40 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="percent"
              nameKey="label"
              innerRadius="58%"
              outerRadius="100%"
              paddingAngle={1.5}
              stroke={CHART.surface}
              strokeWidth={2}
              isAnimationActive={animate}
            >
              {data.map((slice) => (
                <Cell key={slice.label} fill={slice.color} />
              ))}
            </Pie>
            <Tooltip content={<AllocationTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <ul className="w-full space-y-1.5 text-sm sm:flex-1">
        {data.map((slice) => (
          <li key={slice.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: slice.color }} aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate">{slice.label}</span>
            <span className="font-mono text-xs font-semibold text-ink-soft">
              {Math.round(slice.percent)}%
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

function AllocationTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-semibold">{row.label}</p>
      <p className="mt-0.5 font-mono">{Math.round(row.percent)}% of use</p>
      {row.note && <p className="mt-1 max-w-[12rem] text-ink-soft">{row.note}</p>}
    </div>
  );
}
