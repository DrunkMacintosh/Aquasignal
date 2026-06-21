// Floating status banner over the map. `tone`: critical (solid deep-red bar,
// role=alert), warn (warm amber card), info (quiet paper card). Optional icon,
// dismiss button, and trailing actions. Presentational only.
const TONES = {
  critical: 'bg-risk-critical text-white border-risk-critical/40',
  warn: 'bg-[#FFF8E1] text-ink border-risk-medium/60',
  info: 'bg-surface text-ink border-ink/10',
};

export default function Banner({ tone = 'info', icon, children, onDismiss, actions, className = '', ...rest }) {
  return (
    <div
      role={tone === 'critical' ? 'alert' : 'status'}
      className={`pointer-events-auto flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm shadow-card animate-fade-up ${TONES[tone] ?? TONES.info} ${className}`}
      {...rest}
    >
      {icon && <span aria-hidden="true" className="shrink-0">{icon}</span>}
      <div className="min-w-0 flex-1">{children}</div>
      {actions}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="-mr-1 shrink-0 px-0.5 text-lg leading-none opacity-80 hover:opacity-100"
        >
          ×
        </button>
      )}
    </div>
  );
}
