import { formatMonth, riskBand, trendInfo } from '../lib/risk.js';

const TREND_TONES = {
  bad: 'border-risk-critical/30 bg-risk-critical/10 text-risk-critical',
  good: 'border-risk-low/40 bg-risk-low/15 text-[#2E7D32]',
  neutral: 'border-ink/15 bg-ink/5 text-ink-soft',
};

/** Big colour-coded score with the trend badge beside it. */
export default function RiskScoreCard({ risk, trend, month, label = 'Current risk' }) {
  const band = riskBand(risk);
  const trendMeta = trendInfo(trend);

  return (
    <div
      className="overflow-hidden rounded-xl border border-ink/10"
      aria-label={`Current risk ${Number(risk).toFixed(0)} out of 100, ${band.label}. Trend: ${trendMeta.label}.`}
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
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TREND_TONES[trendMeta.tone]}`}
        >
          <span aria-hidden="true">{trendMeta.arrow}</span> {trendMeta.label}
        </span>
        {month && <span className="microlabel">Scores · {formatMonth(month)}</span>}
      </div>
    </div>
  );
}
