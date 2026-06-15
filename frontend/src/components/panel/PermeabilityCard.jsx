// Soil permeability + derived recharge potential, shown beside the risk score.
// Aquifers refill by infiltration through permeable ground, so a unit's
// recharge potential = how freely water soaks in (permeability) x how much
// water is actually available (precipitation - evapotranspiration). The
// recharge value is a relative indicator, not a measured recharge rate.
import { formatMonth } from '../../lib/risk.js';
import { ChartSkeleton } from '../Skeletons.jsx';

const cap = (text) => (text ? text.charAt(0).toUpperCase() + text.slice(1) : text);

export default function PermeabilityCard({ data, isLoading, isError }) {
  if (isLoading) return <ChartSkeleton height={120} />;
  if (isError) {
    return <p className="text-sm text-ink-soft">Permeability data could not be loaded.</p>;
  }
  if (!data?.has_data) {
    return (
      <p className="text-sm text-ink-soft">
        No soil permeability data for this area — its cells fall outside the soil grid.
      </p>
    );
  }

  const pct = Math.round((data.permeability_index ?? 0) * 100);
  const hasRecharge = data.recharge_value != null;

  return (
    <div
      className="overflow-hidden rounded-lg border border-ink/10"
      aria-label={`Soil permeability ${data.permeability_class}. Recharge potential ${
        hasRecharge ? `${data.recharge_label}, ${data.recharge_value} millimetre equivalent` : 'unavailable'
      }.`}
    >
      <div className="px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm font-semibold">Soil permeability</p>
          <p className="font-display text-lg font-semibold text-[#0E6E83]">
            {cap(data.permeability_class)}
          </p>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink/10" aria-hidden="true">
          <div className="h-full rounded-full bg-[#0E6E83]" style={{ width: `${pct}%` }} />
        </div>
        <p className="microlabel mt-1.5">
          Ksat ≈ {data.soil_ksat_mm_hr?.toFixed(1)} mm/hr · index {data.permeability_index?.toFixed(2)}
        </p>
      </div>

      <div className="border-t border-ink/10 bg-paper/60 px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm font-semibold">Recharge potential</p>
          {hasRecharge ? (
            <p className="font-mono text-sm font-semibold">
              {data.recharge_value.toFixed(0)}
              <span className="ml-1 text-[10px] font-normal text-ink-faint">mm-eq</span>
            </p>
          ) : (
            <p className="text-xs text-ink-soft">—</p>
          )}
        </div>
        {hasRecharge ? (
          <p className="mt-1 text-[11px] leading-snug text-ink-faint">
            {cap(data.recharge_label)} — {data.net_infiltration_mm?.toFixed(0)} mm of net infiltration
            (rain minus evapotranspiration{data.month ? `, ${formatMonth(data.month)}` : ''}) soaking
            through {data.permeability_class} ground. Relative indicator, not a measured recharge rate.
          </p>
        ) : (
          <p className="mt-1 text-[11px] leading-snug text-ink-faint">
            No water-balance reading for the latest month, so recharge can’t be estimated.
          </p>
        )}
      </div>
    </div>
  );
}
