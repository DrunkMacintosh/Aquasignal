// Base surface of the design system: frosted-glass instrument panel — a
// translucent near-white fill with backdrop blur, a hairline edge, and a lit
// top highlight (see `.card` in index.css). The shell for every floating
// element over the map. Pass `ticks` to add precision corner marks.
export default function Card({
  children,
  padding = 16,
  as: Tag = 'div',
  ticks = false,
  className = '',
  style,
  ...rest
}) {
  const pad = typeof padding === 'number' ? `${padding}px` : padding;
  return (
    <Tag
      className={`card ${ticks ? 'corner-ticks' : ''} ${className}`}
      style={{ padding: pad, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
