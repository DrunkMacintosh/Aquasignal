// Raw satellite observations — the model's inputs, shown beside its output so
// staff can see *why* a risk score is what it is. One row per variable:
// label, 24-month mini-trend, latest reading.
import { Line, LineChart, ResponsiveContainer } from 'recharts';
import { SATELLITE_VARIABLES, latestPoint, variableSeries } from '../lib/satellite.js';
import { formatMonth } from '../lib/risk.js';
import { ChartSkeleton } from './Skeletons.jsx';

export default function SatelliteObservations({ observations, isLoading, isError }) {
  if (isLoading) return <ChartSkeleton height={180} />;
  if (isError) {
    return <p className="text-sm text-ink-soft">Satellite observations could not be loaded.</p>;
  }

  const rows = SATELLITE_VARIABLES.map((variable) => ({
    ...variable,
    series: variableSeries(observations, variable.key),
  })).filter((row) => row.series.length > 0);

  if (rows.length === 0) {
    return <p className="text-sm text-ink-soft">No satellite observations for this area yet.</p>;
  }

  const latestMonth = latestPoint(rows[0].series)?.month;

  return (
    <div className="overflow-hidden rounded-lg border border-ink/10">
      <ul className="divide-y divide-ink/10">
        {rows.map((row) => (
          <VariableRow key={row.key} row={row} />
        ))}
      </ul>
      <p className="border-t border-ink/10 bg-paper/60 px-3 py-1.5 text-[11px] text-ink-soft">
        Raw sensor readings{latestMonth ? ` to ${formatMonth(latestMonth)}` : ''} — these feed
        the risk model, they are not the risk score.
      </p>
    </div>
  );
}

function VariableRow({ row }) {
  const latest = latestPoint(row.series);
  return (
    <li
      className="px-3 py-2"
      aria-label={`${row.label}: latest ${latest.value.toFixed(row.precision)} ${row.unit}. ${row.hint ?? ''}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-36 shrink-0">
          <p className="text-xs font-semibold leading-tight">{row.label}</p>
          <p className="microlabel mt-0.5">{row.source}</p>
        </div>
        <div className="h-9 min-w-0 flex-1" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={row.series} margin={{ top: 4, right: 2, bottom: 4, left: 2 }}>
              <Line
                dataKey="value"
                stroke="#0E6E83"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="w-20 shrink-0 text-right font-mono text-sm font-semibold">
          {latest.value.toFixed(row.precision)}
          <span className="ml-1 text-[10px] font-normal text-ink-faint">{row.unit}</span>
        </p>
      </div>
      {row.hint && (
        <p className="mt-1 text-[10px] leading-snug text-ink-faint">{row.hint}</p>
      )}
    </li>
  );
}
