// The 2-year risk history as a floating popout beside the overview, mirroring
// AdvisorPopout's docking (left of the right-docked panel on desktop, full
// screen on mobile). Escape/close are handled by DistrictPanel.
//
// It re-reads useDistrictHistory(district): same React Query key the overview
// already used, so this is a cache hit, not a second network round-trip.
import { useDistrictHistory } from '../../api/hooks.js';
import HistoryChart from '../HistoryChart.jsx';

export default function HistoryPopout({ district, onClose, onSelectMonth }) {
  const history = useDistrictHistory(district);
  const monthly = history.data?.monthly;

  return (
    <aside
      role="dialog"
      aria-label={`Risk history for ${district}`}
      className="fixed inset-0 z-40 flex flex-col bg-surface shadow-sheet animate-fade-up md:absolute md:inset-auto md:left-[14rem] md:right-[26.5rem] md:top-[5.5rem] md:max-h-[calc(100vh-9.5rem)] md:rounded-2xl md:border md:border-ink/10 md:shadow-card md:animate-slide-in-right"
    >
      <header className="flex items-start justify-between gap-3 border-b border-ink/10 px-5 py-4">
        <div className="min-w-0">
          <h2 className="truncate font-display text-lg font-semibold leading-tight">
            Risk history
          </h2>
          <p className="microlabel mt-1">
            {district} · Full history · observed
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close history"
          className="shrink-0 rounded-lg border border-ink/10 px-2.5 py-1 text-lg leading-none text-ink-soft transition-colors hover:bg-paper hover:text-ink"
        >
          ×
        </button>
      </header>

      <div className="panel-scroll min-h-0 flex-1 overflow-y-auto p-5">
        {history.isError ? (
          <p className="text-sm text-ink-soft">History could not be loaded.</p>
        ) : (
          <HistoryChart
            points={monthly}
            isLoading={history.isPending}
            onSelectMonth={onSelectMonth}
          />
        )}
      </div>
    </aside>
  );
}
