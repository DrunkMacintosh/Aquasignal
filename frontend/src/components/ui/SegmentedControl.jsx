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
          className={`rounded-[0.625rem] px-5 py-2.5 text-sm font-semibold transition-all duration-200 ${
            value === option.value
              ? 'bg-gradient-to-b from-[#2a52f0] to-water text-white shadow-[0_6px_18px_-8px_rgba(31,70,229,0.7)]'
              : 'text-ink-soft hover:bg-water-wash hover:text-water-deep'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
