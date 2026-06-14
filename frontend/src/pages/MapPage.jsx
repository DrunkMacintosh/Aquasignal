// Primary view: full-viewport risk map with overlay chrome. Two map views
// share the instance — "Districts" (area-weighted province choropleth,
// default) and "Grid detail" (the model's native 0.25° cells). The header
// row, banners, legend, and toggle float above the map; the detail panel
// docks right (desktop) or rises as a bottom sheet (mobile).
import { lazy, Suspense, useState } from 'react';
import { useDistrictRiskMap, useRiskMap } from '../api/hooks.js';
import { useAuth } from '../context/AuthContext.jsx';
import AlertBanner from '../components/AlertBanner.jsx';
import MapLegend from '../components/MapLegend.jsx';
import RiskMap from '../components/Map.jsx';
import SegmentedControl from '../components/SegmentedControl.jsx';
import StaleDataBanner from '../components/StaleDataBanner.jsx';
import { formatMonth } from '../lib/risk.js';
import { ADMIN_UNIT_LABEL } from '../lib/adminUnits.js';

// The detail panel pulls in Recharts (~150 kB gzipped); loading it on first
// open keeps the chart library out of the map's critical path.
const DistrictPanel = lazy(() => import('../components/DistrictPanel.jsx'));

const VIEW_STORAGE_KEY = 'aquasignal.map-view';

const VIEW_OPTIONS = [
  { value: 'districts', label: `${ADMIN_UNIT_LABEL} view` },
  { value: 'roads', label: 'Road view' },
  { value: 'grid', label: 'Grid view' },
];

export default function MapPage() {
  const [view, setView] = useState(() => {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY);
    return VIEW_OPTIONS.some((option) => option.value === stored) ? stored : 'districts';
  });
  const districtMap = useDistrictRiskMap();
  const gridMap = useRiskMap(view === 'grid'); // heavy cell payload loads on demand
  const { isAuthenticated, isExpiring, promptSignIn, signOut } = useAuth();
  const [selection, setSelection] = useState(null);

  const active = view === 'grid' ? gridMap : districtMap;
  const month = active.data?.month ?? districtMap.data?.month;
  const showStaleBanner = active.isError && active.data;
  const showHardError = active.isError && !active.data;

  function changeView(next) {
    setView(next);
    localStorage.setItem(VIEW_STORAGE_KEY, next);
  }

  function refresh() {
    districtMap.refetch();
    if (view === 'grid') gridMap.refetch();
  }

  return (
    <div className="relative h-full overflow-hidden">
      <RiskMap
        gridData={gridMap.data}
        districtData={districtMap.data}
        view={view}
        month={month}
        selectedCellId={selection?.type === 'cell' ? selection.cell.cell_id : null}
        selectedDistrict={selection?.type === 'district' ? selection.name : null}
        onSelectCell={(cell) => setSelection({ type: 'cell', cell })}
        onSelectDistrict={(props) =>
          setSelection({ type: 'district', name: props.district_name })
        }
        isLoading={active.isPending}
      />

      {/* Floating chrome above the map */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex flex-col gap-2 p-3 md:p-4">
        <div className="flex items-start justify-between gap-3">
          <Brand />
          <StatusCard
            month={month}
            updatedAt={active.dataUpdatedAt}
            isFetching={districtMap.isFetching || gridMap.isFetching}
            isAuthenticated={isAuthenticated}
            onRefresh={refresh}
            onSignIn={promptSignIn}
            onSignOut={signOut}
          />
        </div>
        {isExpiring && <SessionExpiryNotice onSignIn={promptSignIn} />}
        {showStaleBanner && (
          <StaleDataBanner updatedAt={active.dataUpdatedAt} onRetry={refresh} />
        )}
        <AlertBanner onOpenDistrict={(name) => setSelection({ type: 'district', name })} />
      </div>

      <div className="pointer-events-none absolute left-3 top-[4.75rem] z-10 flex flex-col gap-2 md:left-4 md:top-20 [&>*]:pointer-events-auto">
        {/* Every view now shows a risk choropleth (roads = districts over the
            street basemap), so the key is always relevant. */}
        <MapLegend />
      </div>

      {/* View switcher floats centred at the bottom, dynamic-island style,
          clear of the bottom-right zoom and attribution controls. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-4 z-10 flex justify-center md:bottom-6 [&>*]:pointer-events-auto">
        <SegmentedControl options={VIEW_OPTIONS} value={view} onChange={changeView} label="Map view" />
      </div>

      {showHardError && <HardError error={active.error} onRetry={refresh} />}

      <Suspense fallback={null}>
        <DistrictPanel selection={selection} month={month} onClose={() => setSelection(null)} />
      </Suspense>
    </div>
  );
}

function Brand() {
  return (
    <div className="pointer-events-auto card flex items-center gap-2.5 px-3.5 py-2">
      <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden="true">
        <path d="M16 3c5 7 9 11.5 9 17a9 9 0 1 1-18 0c0-5.5 4-10 9-17z" fill="#0E6E83" />
      </svg>
      <div>
        <p className="font-display text-base font-bold leading-none">AquaSignal</p>
        <p className="microlabel mt-0.5 hidden sm:block">Groundwater survey · Mekong Delta</p>
      </div>
    </div>
  );
}

function StatusCard({ month, updatedAt, isFetching, isAuthenticated, onRefresh, onSignIn, onSignOut }) {
  const fetchedTime = updatedAt
    ? new Date(updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

  return (
    <div className="pointer-events-auto card flex items-center gap-2 px-3 py-2 sm:gap-3">
      <div className="hidden text-right sm:block">
        <p className="font-mono text-xs font-semibold">{month ? formatMonth(month) : 'No data'}</p>
        <p className="microlabel">Fetched {fetchedTime}</p>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        disabled={isFetching}
        aria-label="Refresh risk data"
        className="btn-secondary !px-3 !py-1.5 text-xs"
      >
        <span className={isFetching ? 'inline-block animate-spin' : ''} aria-hidden="true">
          ⟳
        </span>
        {isFetching ? 'Updating…' : 'Refresh'}
      </button>
      {isAuthenticated ? (
        <button
          type="button"
          onClick={onSignOut}
          aria-label="Sign out"
          className="rounded-lg px-2 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:bg-paper hover:text-ink"
        >
          Sign out
        </button>
      ) : (
        <button
          type="button"
          onClick={onSignIn}
          aria-label="Sign in"
          className="btn-secondary !px-3 !py-1.5 text-xs"
        >
          Sign in
        </button>
      )}
    </div>
  );
}

function SessionExpiryNotice({ onSignIn }) {
  return (
    <div
      role="status"
      className="pointer-events-auto flex items-center gap-3 rounded-xl border border-risk-medium/60 bg-[#FFF8E1] px-4 py-2.5 shadow-card animate-fade-up"
    >
      <span aria-hidden="true">⏳</span>
      <p className="text-sm font-medium">Your session expires soon.</p>
      <button
        type="button"
        onClick={onSignIn}
        className="ml-auto rounded-md border border-ink/15 bg-surface px-3 py-1 text-xs font-semibold hover:bg-paper"
      >
        Sign in again
      </button>
    </div>
  );
}

function HardError({ error, onRetry }) {
  const detail = error?.response?.data?.detail;
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-paper/80 p-6">
      <div className="card max-w-md p-6 text-center animate-fade-up" role="alert">
        <p className="font-display text-lg font-semibold">Couldn't load risk data</p>
        <p className="mt-2 text-sm text-ink-soft">
          {typeof detail === 'string'
            ? detail
            : 'The AquaSignal server is unreachable. Your network or the service may be down.'}
        </p>
        <button type="button" onClick={onRetry} className="btn-primary mt-5">
          Try again
        </button>
      </div>
    </div>
  );
}
