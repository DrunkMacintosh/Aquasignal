// Small eyebrow/label style — the connective tissue of the UI (section
// eyebrows, field labels, captions). Soft sans (Hanken Grotesk), sentence case,
// gentle tracking; defined once as `.microlabel` in index.css so every label
// stays in sync.
export default function MicroLabel({ children, as: Tag = 'p', className = '', ...rest }) {
  return (
    <Tag className={`microlabel ${className}`} {...rest}>
      {children}
    </Tag>
  );
}
