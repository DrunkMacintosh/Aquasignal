// Base surface of the design system: near-white card on warm paper, hairline
// ink border, soft low shadow, generous rounding. The shell for every floating
// element over the map.
export default function Card({ children, padding = 16, as: Tag = 'div', className = '', style, ...rest }) {
  const pad = typeof padding === 'number' ? `${padding}px` : padding;
  return (
    <Tag
      className={`rounded-xl border border-ink/10 bg-surface shadow-card ${className}`}
      style={{ padding: pad, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
