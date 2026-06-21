// Small pill tag. `tone` picks a tinted surface: neutral, accent (water), or one
// of the four risk bands. Used for source tags, outlook chips, quick-win flags.
const TONES = {
  neutral: 'bg-surface text-ink-faint border-ink/10',
  accent: 'bg-water-wash text-water border-water/35',
  low: 'bg-risk-low/15 text-[#2E7D32] border-risk-low/40',
  medium: 'bg-risk-medium/[0.18] text-[#946200] border-risk-medium/50',
  high: 'bg-risk-high/[0.12] text-[#C2410C] border-risk-high/40',
  critical: 'bg-risk-critical/10 text-risk-critical border-risk-critical/30',
};

export default function Badge({ children, tone = 'neutral', className = '', ...rest }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold leading-snug ${TONES[tone] ?? TONES.neutral} ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}
