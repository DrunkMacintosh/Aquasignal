import { NO_DATA_COLOR, RISK_BANDS } from '../lib/risk.js';

/** Survey-sheet style map key: colour swatch + text label + numeric range. */
export default function MapLegend() {
  return (
    <section className="card w-48 p-3" aria-label="Map legend: well-failure risk bands">
      <h2 className="microlabel">Well-failure risk</h2>
      <dl className="mt-2 space-y-1.5">
        {RISK_BANDS.map((band) => (
          <div key={band.level} className="flex items-center gap-2.5">
            <dt className="flex items-center gap-2.5">
              <span
                className="h-3.5 w-3.5 shrink-0 rounded-sm border border-ink/20"
                style={{ backgroundColor: band.color }}
                aria-hidden="true"
              />
              <span className="text-xs font-semibold">{band.label}</span>
            </dt>
            <dd className="ml-auto font-mono text-[11px] text-ink-faint">
              {band.min}–{band.max}
            </dd>
          </div>
        ))}
        <div className="flex items-center gap-2.5">
          <dt className="flex items-center gap-2.5">
            <span
              className="h-3.5 w-3.5 shrink-0 rounded-sm border border-ink/20"
              style={{ backgroundColor: NO_DATA_COLOR }}
              aria-hidden="true"
            />
            <span className="text-xs font-semibold">No data</span>
          </dt>
          <dd className="ml-auto font-mono text-[11px] text-ink-faint">—</dd>
        </div>
      </dl>
      <p className="mt-2.5 border-t border-ink/10 pt-2 text-[11px] leading-snug text-ink-soft">
        Trend vs. 3 months ago: ↑ worsening · → stable · ↓ improving
      </p>
    </section>
  );
}
