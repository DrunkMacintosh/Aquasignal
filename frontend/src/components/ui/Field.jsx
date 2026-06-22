// Labelled text input: mono microlabel above a paper-bordered field, optional
// hint or error below. Matches the auth-form input exactly. onChange(value).
export default function Field({
  id, label, type = 'text', value, onChange, placeholder, hint, error,
  required = false, autoComplete, className = '', ...rest
}) {
  const errorId = error ? `${id}-error` : undefined;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="microlabel">
          {label}
        </label>
      )}
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        aria-describedby={errorId ?? hintId}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
        className={`mt-1.5 w-full rounded-lg border bg-surface px-3.5 py-2.5 text-sm focus-visible:outline-water ${error ? 'border-risk-critical/45' : 'border-ink/15'}`}
        {...rest}
      />
      {error ? (
        <p id={errorId} className="mt-1.5 text-xs font-medium text-risk-critical">{error}</p>
      ) : hint ? (
        <p id={hintId} className="mt-1 text-xs text-ink-faint">{hint}</p>
      ) : null}
    </div>
  );
}
