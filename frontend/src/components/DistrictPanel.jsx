// Detail panel: right-side card on desktop, bottom sheet under 768px.
// Two modes share the shell:
//   { type: 'cell', cell }      — opened by clicking a grid cell on the map
//   { type: 'district', name }  — opened from the critical-alert banner
import { useEffect, useState } from 'react';
import { formatCellName } from '../lib/risk.js';
import { adminUnitType } from '../lib/adminUnits.js';
import CellDetails from './panel/CellDetails.jsx';
import DistrictDetails from './panel/DistrictDetails.jsx';
import AdvisorPopout from './panel/AdvisorPopout.jsx';
import HistoryPopout from './panel/HistoryPopout.jsx';

export default function DistrictPanel({ selection, month, onClose }) {
  const [advisorOpen, setAdvisorOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  // The popouts belong to one selection; reset them whenever the selection
  // changes (new district) or the panel closes.
  useEffect(() => {
    setAdvisorOpen(false);
    setHistoryOpen(false);
  }, [selection]);

  useEffect(() => {
    if (!selection) return undefined;
    const handleKey = (event) => {
      if (event.key !== 'Escape') return;
      // Escape closes an open popout first, then the panel on a second press.
      if (advisorOpen) setAdvisorOpen(false);
      else if (historyOpen) setHistoryOpen(false);
      else onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [selection, advisorOpen, historyOpen, onClose]);

  if (!selection) return null;

  const isCell = selection.type === 'cell';
  const title = isCell ? formatCellName(selection.cell.cell_id) : selection.name;
  const subtitle = isCell
    ? `Grid cell ${selection.cell.cell_id}`
    : `${adminUnitType(selection.name)} overview`;

  return (
    <>
    <aside
      role="dialog"
      aria-labelledby="panel-title"
      className="fixed inset-x-0 bottom-0 z-30 flex max-h-[78vh] flex-col rounded-t-2xl border-t border-ink/10 bg-surface shadow-sheet animate-fade-up md:absolute md:inset-auto md:bottom-4 md:right-4 md:top-[5.5rem] md:max-h-none md:w-[400px] md:rounded-2xl md:border md:shadow-card"
    >
      {/* Grab handle, mobile only */}
      <div className="flex justify-center pt-2 md:hidden" aria-hidden="true">
        <span className="h-1 w-10 rounded-full bg-ink/20" />
      </div>

      <header className="flex items-start justify-between gap-3 border-b border-ink/10 px-5 py-4">
        <div className="min-w-0">
          <h2 id="panel-title" className="truncate font-display text-xl font-semibold leading-tight">
            {title}
          </h2>
          <p className="microlabel mt-1">{subtitle}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          className="shrink-0 rounded-lg border border-ink/10 px-2.5 py-1 text-lg leading-none text-ink-soft transition-colors hover:bg-paper hover:text-ink"
        >
          ×
        </button>
      </header>

      <div className="panel-scroll min-h-0 flex-1 overflow-y-auto">
        {isCell ? (
          <CellDetails cell={selection.cell} month={month} />
        ) : (
          <DistrictDetails
            name={selection.name}
            month={month}
            // The two popouts share the same docking area, so opening one
            // dismisses the other.
            onPlanWithAi={() => {
              setHistoryOpen(false);
              setAdvisorOpen(true);
            }}
            onSeeHistory={() => {
              setAdvisorOpen(false);
              setHistoryOpen(true);
            }}
          />
        )}
      </div>
    </aside>

    {advisorOpen && !isCell && (
      <AdvisorPopout district={selection.name} onClose={() => setAdvisorOpen(false)} />
    )}
    {historyOpen && !isCell && (
      <HistoryPopout district={selection.name} onClose={() => setHistoryOpen(false)} />
    )}
    </>
  );
}
