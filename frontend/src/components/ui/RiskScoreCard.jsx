import { useEffect, useRef, useState } from 'react';
import { formatMonth, riskBand } from '../../lib/risk.js';
import TrendBadge from './TrendBadge.jsx';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Count a number up from 0 to `target` on mount (easeOutCubic). Snaps straight
// to the final value when the user prefers reduced motion.
function useCountUp(target, duration = 900) {
  const safeTarget = Number.isFinite(target) ? target : 0;
  const [value, setValue] = useState(() => (prefersReducedMotion() ? safeTarget : 0));
  const rafRef = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(safeTarget);
      return undefined;
    }
    let start;
    const step = (now) => {
      if (start === undefined) start = now;
      const t = Math.min(1, (now - start) / duration);
      setValue(safeTarget * (1 - Math.pow(1 - t, 3)));
      if (t < 1) rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [safeTarget, duration]);

  return value;
}

/** Big colour-coded score with the trend badge beside it. */
export default function RiskScoreCard({ risk, trend, month, label = 'Current risk' }) {
  const band = riskBand(risk);
  const shown = useCountUp(Number(risk));

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
          <p className="text-[11px] font-semibold tracking-[0.01em] opacity-80">
            {label}
          </p>
          <p className="font-mono text-5xl font-semibold leading-none tracking-tight tabular-nums">
            {Math.round(shown)}
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
