// AI estimate: recommended actions grouped by timeframe, each scored for impact
// and effort (1-5) shown as pip meters. High-impact / low-effort actions are
// flagged "quick win" so users can see where to start.
import { CHART } from '../../../lib/reportManifest.js';
import { Badge, MicroLabel } from '../../ui';

// Canonical timeframe ordering; unknown timeframes fall to the end in first-seen
// order.
const TIMEFRAME_ORDER = ['immediate', 'short', 'medium', 'long'];

function timeframeRank(timeframe) {
  const t = (timeframe || '').toLowerCase();
  const idx = TIMEFRAME_ORDER.findIndex((k) => t.includes(k));
  return idx === -1 ? TIMEFRAME_ORDER.length : idx;
}

export default function PriorityActions({ actions = [] }) {
  const rows = (actions ?? []).filter((a) => a.action);
  if (!rows.length) return null;

  // Stable group order by timeframe, then by impact desc / effort asc within.
  const groups = [];
  const byTimeframe = new Map();
  for (const a of rows) {
    const key = a.timeframe || 'Other';
    if (!byTimeframe.has(key)) {
      byTimeframe.set(key, []);
      groups.push(key);
    }
    byTimeframe.get(key).push(a);
  }
  groups.sort((x, y) => timeframeRank(x) - timeframeRank(y));

  return (
    <div className="space-y-3" aria-label="Priority actions">
      {groups.map((timeframe) => {
        const items = byTimeframe.get(timeframe).slice().sort(
          (a, b) => (b.impact ?? 0) - (a.impact ?? 0) || (a.effort ?? 0) - (b.effort ?? 0),
        );
        return (
          <div key={timeframe}>
            {timeframe !== 'Other' && (
              <p className="text-xs font-semibold uppercase tracking-wide text-water">{timeframe}</p>
            )}
            <ul className="mt-1.5 space-y-1.5">
              {items.map((a, i) => (
                <ActionRow key={`${timeframe}-${i}`} action={a} />
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

function ActionRow({ action }) {
  const { action: text, detail = '', steps = [], benefit = '', impact = 0, effort = 0 } = action;
  const quickWin = impact >= 4 && effort > 0 && effort <= 2;
  return (
    <li className="rounded-lg border border-ink/10 bg-surface px-3 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm font-semibold leading-snug">{text}</p>
        {quickWin && (
          <Badge tone="accent" className="shrink-0 !px-1.5 !py-0.5 !text-[10px]">
            quick win
          </Badge>
        )}
      </div>

      {detail && <p className="mt-1 text-xs leading-relaxed text-ink-soft">{detail}</p>}

      {steps.length > 0 && (
        <ol className="mt-1.5 list-decimal space-y-0.5 pl-4 text-xs leading-relaxed text-ink marker:text-ink-faint">
          {steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}

      {benefit && (
        <p className="mt-1.5 text-xs leading-relaxed text-ink">
          <span className="font-semibold text-water">Outcome: </span>
          {benefit}
        </p>
      )}

      <div className="mt-2 flex items-center gap-4 text-[11px] text-ink-soft">
        <Pips label="Impact" value={impact} color={CHART.water} />
        <Pips label="Effort" value={effort} color={CHART.inkFaint} />
      </div>
    </li>
  );
}

function Pips({ label, value, color }) {
  if (!value) return null;
  return (
    <span className="flex items-center gap-1" aria-label={`${label} ${value} of 5`}>
      <MicroLabel>{label}</MicroLabel>
      <span className="flex gap-0.5" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((n) => (
          <span
            key={n}
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: n <= value ? color : 'rgba(28,43,51,0.15)' }}
          />
        ))}
      </span>
    </span>
  );
}
