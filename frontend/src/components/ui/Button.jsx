// Action button tuned to the Daylight Lab palette. Three variants: electric
// cobalt `primary` (gradient + glow-and-lift on hover), frosted `secondary`,
// and quiet `ghost`. Renders an <a> when `href` is given.
const BASE =
  'inline-flex items-center justify-center gap-2 rounded-[0.625rem] font-semibold transition-all duration-200 focus-visible:outline-water disabled:cursor-not-allowed disabled:opacity-50';
const SIZES = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2.5 text-sm' };
const VARIANTS = {
  primary:
    'border border-transparent bg-gradient-to-b from-[#2a52f0] to-water text-white shadow-[0_1px_2px_rgba(11,31,51,0.18),0_8px_20px_-10px_rgba(31,70,229,0.6)] hover:from-water hover:to-water-deep hover:shadow-glow hover:-translate-y-px active:translate-y-0',
  secondary:
    'border border-ink/15 bg-white/70 backdrop-blur text-ink hover:border-water/45 hover:bg-water-wash hover:text-water-deep',
  ghost: 'border border-transparent text-ink-soft hover:bg-water-wash hover:text-water-deep',
};

export default function Button({
  children, variant = 'primary', size = 'md', fullWidth = false,
  href, type = 'button', disabled = false, className = '', onClick, ...rest
}) {
  const cls = `${BASE} ${SIZES[size] ?? SIZES.md} ${VARIANTS[variant] ?? VARIANTS.primary} ${fullWidth ? 'w-full' : ''} ${className}`;
  if (href) {
    return (
      <a href={href} className={cls} onClick={disabled ? undefined : onClick} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <button type={type} disabled={disabled} className={cls} onClick={onClick} {...rest}>
      {children}
    </button>
  );
}
