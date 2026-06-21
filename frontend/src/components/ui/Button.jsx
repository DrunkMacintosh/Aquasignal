// Primary action button tuned to the survey-ledger palette. Three variants:
// solid water `primary`, paper-bordered `secondary`, quiet `ghost`. Renders an
// <a> when `href` is given.
const BASE =
  'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors focus-visible:outline-water disabled:cursor-not-allowed disabled:opacity-50';
const SIZES = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2.5 text-sm' };
const VARIANTS = {
  primary: 'border border-transparent bg-water text-white hover:bg-water-deep',
  secondary: 'border border-ink/15 bg-surface text-ink hover:border-ink/30 hover:bg-paper',
  ghost: 'border border-transparent text-ink-soft hover:bg-paper hover:text-ink',
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
