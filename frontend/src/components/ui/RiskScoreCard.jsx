import { formatMonth, riskBand } from '../../lib/risk.js';
import TrendBadge from './TrendBadge.jsx';

/** Big colour-coded score with the trend badge beside it. */
export default function RiskScoreCard({ risk, trend, month, label = 'Current risk' }) {
  const band = riskBand(risk);

  return (
    <div
      className="overflow-hidden rounded-[0.875rem] border border-ink/10 shadow-card"
      aria-label={`Current risk ${Number(risk).toFixed(0)} out of 100, ${band.label}.`}
    >
      <div
        className="flex items-end justify-between gap-4 px-5 py-4"
        style={{ backgroundColor: band.color, color: band.onColor }}
      >
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] opacity-80">
            {label}
          </p>
          <p className="font-mono text-5xl font-semibold leading-none tracking-tight">
            {Number(risk).toFixed(0)}
            <span className="text-xl opacity-70">/100</span>
          </p>
        </div>
        <p className="font-display text-xl font-semibold">{band.label}</p>
      </div>
      <div className="flex items-center justify-between bg-surface px-5 py-2.5">
        <TrendBadge trend={trend} />
        {month && <span className="microlabel">Scores · {formatMonth(month)}</span>}
      </div>
    </div>
  );
}
