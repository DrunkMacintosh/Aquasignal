// The advisor as a floating popout beside the overview. On desktop it docks
// just to the LEFT of the right-docked overview panel (side-by-side); on mobile
// it covers the screen. Escape/close are handled by DistrictPanel so a single
// Escape closes the popout before the overview.
import AdvisorPlanner from './AdvisorPlanner.jsx';

export default function AdvisorPopout({ district, onClose }) {
  return (
    <aside
      role="dialog"
      aria-label="Plan your water use with AI"
      className="fixed inset-0 z-40 flex flex-col bg-surface shadow-sheet animate-fade-up md:absolute md:inset-auto md:bottom-4 md:right-[26.5rem] md:top-[5.5rem] md:w-[380px] md:rounded-2xl md:border md:border-ink/10 md:shadow-card"
    >
      <header className="flex items-start justify-between gap-3 border-b border-ink/10 px-5 py-4">
        <div className="min-w-0">
          <h2 className="truncate font-display text-lg font-semibold leading-tight">
            Plan your water use with AI
          </h2>
          <p className="microlabel mt-1">{district}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close planner"
          className="shrink-0 rounded-lg border border-ink/10 px-2.5 py-1 text-lg leading-none text-ink-soft transition-colors hover:bg-paper hover:text-ink"
        >
          ×
        </button>
      </header>

      <div className="panel-scroll min-h-0 flex-1 overflow-y-auto p-5">
        <AdvisorPlanner key={district} district={district} />
      </div>
    </aside>
  );
}
