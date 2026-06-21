import { trendInfo } from '../../lib/risk.js';

const TONES = {
  bad: 'border-risk-critical/30 bg-risk-critical/10 text-risk-critical',
  good: 'border-risk-low/40 bg-risk-low/15 text-[#2E7D32]',
  neutral: 'border-ink/15 bg-ink/5 text-ink-soft',
};

// Trend pill — ↑ worsening / → stable / ↓ improving. Shared by RiskScoreCard
// and available standalone for rows and tables.
export default function TrendBadge({ trend, className = '' }) {
  const t = trendInfo(trend);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONES[t.tone]} ${className}`}>
      <span aria-hidden="true">{t.arrow}</span> {t.label}
    </span>
  );
}
