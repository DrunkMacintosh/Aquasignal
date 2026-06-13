/**
 * Small segmented control used for the map view (Districts/Grid) and the
 * basemap (Satellite/Streets) switches.
 * options: [{ value, label }]
 */
export default function SegmentedControl({ options, value, onChange, label }) {
  return (
    <div className="card flex p-1" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
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
