// IBM Plex Mono, 10px, uppercase, wide tracking, soft ink — the connective
// tissue of the survey-ledger look (section eyebrows, field labels, captions).
export default function MicroLabel({ children, as: Tag = 'p', className = '', ...rest }) {
  return (
    <Tag className={`font-mono text-[10px] uppercase tracking-[0.18em] text-ink-soft ${className}`} {...rest}>
      {children}
    </Tag>
  );
}
