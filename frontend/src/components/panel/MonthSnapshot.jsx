// A single month's snapshot, opened by clicking a point on the history graph.
// Mirrors the province overview's sections but for one past month and without
// the forward-looking forecast or the AI plan: that month's risk score and the
// trajectory it had then, its raw satellite readings, and the (static) soil
// permeability.
import {
  useDistrictHistory,
  useDistrictPermeability,
  useDistrictSatellite,
} from '../../api/hooks.js';
import { formatMonth, trendAtMonth } from '../../lib/risk.js';
import { SATELLITE_VARIABLES } from '../../lib/satellite.js';
import { ChartSkeleton, PanelSkeleton } from '../Skeletons.jsx';
import { RiskScoreCard } from '../ui';
import PermeabilityCard from './PermeabilityCard.jsx';
import SectionTitle from './SectionTitle.jsx';

// The whole observed record, so any clicked month is reachable — the default
// 24-month satellite window wouldn't cover a point from years ago.
const SATELLITE_FULL_MONTHS = 200;

export default function MonthSnapshot({ name, month, onBack }) {
  const history = useDistrictHistory(name);
  const satellite = useDistrictSatellite(name, SATELLITE_FULL_MONTHS);
  const permeability = useDistrictPermeability(name);

  const monthly = history.data?.monthly ?? [];
  const point = monthly.find((entry) => entry.month === month) ?? null;
  const trend = trendAtMonth(monthly, month);
  const observation = satellite.data?.observations?.find((row) => row.month === month);

  return (
    <div className="stagger space-y-6 p-5">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 rounded-lg border border-ink/10 px-2.5 py-1 text-xs font-semibold text-ink-soft transition-colors hover:bg-paper hover:text-ink focus-visible:outline-water"
      >
        <span aria-hidden="true">←</span> Back to overview
      </button>

      {history.isPending ? (
        <PanelSkeleton />
      ) : point ? (
        <RiskScoreCard risk={point.risk} trend={trend} month={point.month} label="Risk score" />
      ) : (
        <p className="text-sm text-ink-soft">
          No risk score recorded for {formatMonth(month)}.
        </p>
      )}

      <section aria-label="Satellite readings for this month">
        <SectionTitle>Satellite readings · {formatMonth(month)}</SectionTitle>
        <MonthReadings
          observation={observation}
          month={month}
          isLoading={satellite.isPending}
          isError={satellite.isError}
        />
      </section>

      <section aria-label="Permeability and recharge">
        <SectionTitle>Permeability &amp; recharge</SectionTitle>
        <PermeabilityCard
          data={permeability.data}
          isLoading={permeability.isPending}
          isError={permeability.isError}
        />
      </section>
    </div>
  );
}

/** Each satellite variable's value for one month (vs the overview's mini-trends). */
function MonthReadings({ observation, month, isLoading, isError }) {
  if (isLoading) return <ChartSkeleton height={140} />;
  if (isError) {
    return <p className="text-sm text-ink-soft">Satellite readings could not be loaded.</p>;
  }

  const rows = SATELLITE_VARIABLES.map((variable) => ({
    ...variable,
    value: observation?.[variable.key],
  })).filter((row) => row.value != null);

  if (rows.length === 0) {
    return (
      <p className="text-sm text-ink-soft">
        No satellite readings for {formatMonth(month)} — this month falls in a sensor gap.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-ink/10 overflow-hidden rounded-lg border border-ink/10">
      {rows.map((row) => (
        <li key={row.key} className="flex items-center justify-between gap-3 px-3 py-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold leading-tight">{row.label}</p>
            <p className="microlabel mt-0.5">{row.source}</p>
          </div>
          <p className="shrink-0 font-mono text-sm font-semibold">
            {Number(row.value).toFixed(row.precision)}
            <span className="ml-1 text-[10px] font-normal text-ink-faint">{row.unit}</span>
          </p>
        </li>
      ))}
    </ul>
  );
}
