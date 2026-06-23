// AI estimate: the advisor's key targets — where a metric stands now vs. the
// recommended target. Rendered as labelled progress bars (not recharts) so
// mixed units (/100, %, m3/mo, days) never get plotted on a shared axis. A tick
// marks the target; the bar turns amber when the current value is off-target.
import { CHART } from '../../../lib/reportManifest.js';

export default function KpiGauges({ metrics = [], animate = false }) {
  const rows = (metrics ?? []).filter((m) => m.label && m.value != null);
  if (!rows.length) return null;

  return (
    <ul className="space-y-3" aria-label="Key targets">
      {rows.map((m) => (
        <Gauge key={m.label} metric={m} animate={animate} />
      ))}
    </ul>
  );
}

function Gauge({ metric, animate = false }) {
  const { label, value, target, unit, direction = 'lower_is_better' } = metric;
  const hasTarget = target != null;
  const onTrack = hasTarget
    ? direction === 'higher_is_better'
      ? value >= target
      : value <= target
    : null;

  // Scale the track so both the value and the target fit with a little headroom.
  const scale = Math.max(value, hasTarget ? target : 0, 1) * 1.15;
  const valuePct = Math.min(100, (value / scale) * 100);
  const targetPct = hasTarget ? Math.min(100, (target / scale) * 100) : null;
  const fill = onTrack === false ? CHART.risk.high : CHART.water;

  return (
    <li>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        <span className="font-mono text-sm font-semibold" style={{ color: fill }}>
          {formatNum(value)}
          {unit && <span className="ml-0.5 text-[10px] font-normal text-ink-faint">{unit}</span>}
        </span>
      </div>
      <div className="relative mt-1 h-2 rounded-full bg-water-wash" role="presentation">
        <div
          className={`h-full rounded-full ${animate ? 'origin-left animate-grow-x' : ''}`}
          style={{ width: `${valuePct}%`, background: fill }}
        />
        {targetPct != null && (
          <span
            className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2 rounded bg-ink"
            style={{ left: `${targetPct}%` }}
            aria-hidden="true"
          />
        )}
      </div>
      {hasTarget && (
        <p className="mt-0.5 text-[11px] text-ink-soft">
          Target: <span className="font-mono">{formatNum(target)}{unit && ` ${unit}`}</span>
          {onTrack != null && (
            <span className="ml-1.5 font-semibold" style={{ color: onTrack ? CHART.risk.low : CHART.risk.high }}>
              · {onTrack ? 'on track' : 'needs action'}
            </span>
          )}
        </p>
      )}
    </li>
  );
}

function formatNum(n) {
  if (n == null) return '—';
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}
