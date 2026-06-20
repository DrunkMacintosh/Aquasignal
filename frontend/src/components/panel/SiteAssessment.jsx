// "Your site" — the figures CALCULATED from the user's own inputs (not AI, not
// satellite): a stat grid plus a small comparison bar chart (e.g. current vs.
// efficient water use). Driven by lib/siteProfile.js compute output.
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
import { CHART } from '../../lib/reportManifest.js';

// "Now" reads as the warm current-state colour; the improved/target bar reads
// green to signal the healthier outcome.
const TONE = { current: '#C8612E', target: CHART.risk.low };

export default function SiteAssessment({ site }) {
  if (!site?.metrics?.length) return null;
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        {site.metrics.map((m) => (
          <div key={m.label}>
            <dt className="microlabel">{m.label}</dt>
            <dd className="mt-0.5 font-mono text-lg font-semibold leading-none">
              {formatValue(m.value)}
              {m.unit && <span className="ml-1 text-[10px] font-normal text-ink-faint">{m.unit}</span>}
            </dd>
            {m.note && <p className="mt-0.5 text-[10px] leading-snug text-ink-soft">{m.note}</p>}
          </div>
        ))}
      </dl>
      {site.comparison?.bars?.length > 0 && <Comparison comparison={site.comparison} />}
    </div>
  );
}

function Comparison({ comparison }) {
  const data = comparison.bars.map((b) => ({
    label: b.label,
    value: b.value,
    color: TONE[b.tone] ?? CHART.water,
  }));

  return (
    <figure aria-label={comparison.title}>
      <figcaption className="microlabel mb-1">{comparison.title}</figcaption>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={data} margin={{ top: 16, right: 8, bottom: 0, left: -18 }}>
          <XAxis
            dataKey="label"
            interval={0}
            tick={{ fontSize: 10, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            tickLine={false}
            axisLine={{ stroke: CHART.axis }}
          />
          <YAxis
            tick={{ fontSize: 10, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip content={<CompTooltip unit={comparison.unit} />} cursor={{ fill: 'rgba(28,43,51,0.04)' }} />
          <Bar dataKey="value" radius={[3, 3, 0, 0]} isAnimationActive={false} maxBarSize={72}>
            {data.map((d) => (
              <Cell key={d.label} fill={d.color} />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              formatter={(v) => formatValue(v)}
              style={{ fontSize: 10, fontFamily: CHART.mono, fill: CHART.inkSoft }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <figcaption className="mt-1 text-[11px] text-ink-soft">
        Calculated from your inputs using representative coefficients — refine with local figures.
      </figcaption>
    </figure>
  );
}

function CompTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs">
      <p className="font-semibold">{label}</p>
      <p className="mt-0.5 font-mono">
        {formatValue(payload[0].value)} {unit}
      </p>
    </div>
  );
}

function formatValue(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  return Number.isInteger(n)
    ? n.toLocaleString()
    : n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}
