/**
 * Segmented control for the map view switch (District/Province/City · Grid ·
 * Roads). Sized as a prominent bottom-centre "dynamic island" bar.
 * options: [{ value, label }]
 */
export default function SegmentedControl({ options, value, onChange, label }) {
  return (
    <div className="card flex p-1.5" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors ${
            value === option.value
              ? 'bg-ink text-white'
              : 'text-ink-soft hover:bg-paper hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
