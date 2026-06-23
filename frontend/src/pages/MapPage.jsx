// Primary view: full-viewport risk map with overlay chrome. Two map views
// share the instance — "Districts" (area-weighted province choropleth,
// default) and "Grid detail" (the model's native 0.25° cells). The header
// row, banners, legend, and toggle float above the map; the detail panel
// docks right (desktop) or rises as a bottom sheet (mobile).
import { lazy, Suspense, useState } from 'react';
import { useDistrictRiskMap, useRiskMap } from '../api/hooks.js';
import { useAuth } from '../context/AuthContext.jsx';
import AlertBanner from '../components/AlertBanner.jsx';
import { Banner, Button, Card, MicroLabel, RiskLegend, SegmentedControl } from '../components/ui';
import RiskMap from '../components/Map.jsx';
import StaleDataBanner from '../components/StaleDataBanner.jsx';
import { formatMonth } from '../lib/risk.js';
import { ADMIN_UNIT_LABEL } from '../lib/adminUnits.js';

// The detail panel pulls in Recharts (~150 kB gzipped); loading it on first
// open keeps the chart library out of the map's critical path.
const DistrictPanel = lazy(() => import('../components/DistrictPanel.jsx'));

const VIEW_STORAGE_KEY = 'aquasignal.map-view';
const BASEMAP_STORAGE_KEY = 'aquasignal.map-basemap';

const VIEW_OPTIONS = [
  { value: 'districts', label: `${ADMIN_UNIT_LABEL} view` },
  { value: 'roads', label: 'Road view' },
  { value: 'grid', label: 'Grid view' },
];

// Imagery basemap behind the risk choropleth: photographic satellite or the
// pale "Atlas" cartographic canvas (crisper for reading risk in daylight).
const BASEMAP_OPTIONS = [
  { value: 'satellite', label: 'Satellite' },
  { value: 'atlas', label: 'Atlas' },
];

export default function MapPage() {
  const [view, setView] = useState(() => {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY);
    return VIEW_OPTIONS.some((option) => option.value === stored) ? stored : 'districts';
  });
  const [basemap, setBasemap] = useState(() => {
    const stored = localStorage.getItem(BASEMAP_STORAGE_KEY);
    return BASEMAP_OPTIONS.some((option) => option.value === stored) ? stored : 'satellite';
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

  function changeBasemap(next) {
    setBasemap(next);
    localStorage.setItem(BASEMAP_STORAGE_KEY, next);
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
        basemap={basemap}
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

      <div className="pointer-events-none absolute left-3 top-[4.75rem] z-10 flex animate-fade-up flex-col gap-2 [animation-delay:160ms] md:left-4 md:top-20 [&>*]:pointer-events-auto">
        {/* Every view now shows a risk choropleth (roads = districts over the
            street basemap), so the key is always relevant. */}
        <RiskLegend />
        <BasemapToggle value={basemap} onChange={changeBasemap} />
      </div>

      {/* View switcher floats centred at the bottom, dynamic-island style,
          clear of the bottom-right zoom and attribution controls. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-4 z-10 flex animate-fade-up justify-center [animation-delay:240ms] md:bottom-6 [&>*]:pointer-events-auto">
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
    <Card ticks padding="9px 15px" className="pointer-events-auto flex items-center gap-3 animate-fade-up">
      <svg
        viewBox="0 0 32 32"
        className="h-7 w-7 drop-shadow-[0_2px_7px_rgba(31,70,229,0.5)]"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="brand-drop" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#1F46E5" />
            <stop offset="1" stopColor="#0AA2C7" />
          </linearGradient>
        </defs>
        <path d="M16 3c5 7 9 11.5 9 17a9 9 0 1 1-18 0c0-5.5 4-10 9-17z" fill="url(#brand-drop)" />
      </svg>
      <div>
        <p className="font-display text-base font-bold leading-none tracking-tight">
          Aqua<span className="text-water">Signal</span>
        </p>
        <MicroLabel className="mt-1 hidden sm:block">Groundwater survey · Mekong Delta</MicroLabel>
      </div>
    </Card>
  );
}

// Compact glass switch for the imagery basemap, docked under the legend.
function BasemapToggle({ value, onChange }) {
  return (
    <Card padding={5} className="flex w-48 gap-1" role="group" aria-label="Base map">
      {BASEMAP_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${
            value === option.value
              ? 'bg-gradient-to-b from-[#2a52f0] to-water text-white shadow-[0_4px_12px_-6px_rgba(31,70,229,0.7)]'
              : 'text-ink-soft hover:bg-water-wash hover:text-water-deep'
          }`}
        >
          {option.label}
        </button>
      ))}
    </Card>
  );
}

function StatusCard({ month, updatedAt, isFetching, isAuthenticated, onRefresh, onSignIn, onSignOut }) {
  const fetchedTime = updatedAt
    ? new Date(updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—';

  return (
    <Card padding="8px 12px" className="pointer-events-auto flex items-center gap-2 animate-fade-up [animation-delay:90ms] sm:gap-3">
      <div className="hidden text-right sm:block">
        <p className="font-mono text-xs font-semibold tracking-tight">{month ? formatMonth(month) : 'No data'}</p>
        <MicroLabel className="flex items-center justify-end gap-1.5">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full bg-water animate-glow-pulse"
            aria-hidden="true"
          />
          Synced {fetchedTime}
        </MicroLabel>
      </div>
      <Button variant="secondary" size="sm" onClick={onRefresh} disabled={isFetching} aria-label="Refresh risk data">
        <span className={isFetching ? 'inline-block animate-spin' : ''} aria-hidden="true">⟳</span>
        {isFetching ? 'Updating…' : 'Refresh'}
      </Button>
      {isAuthenticated ? (
        <Button variant="ghost" size="sm" onClick={onSignOut} aria-label="Sign out" className="!px-2">
          Sign out
        </Button>
      ) : (
        <Button variant="secondary" size="sm" onClick={onSignIn} aria-label="Sign in">
          Sign in
        </Button>
      )}
    </Card>
  );
}

function SessionExpiryNotice({ onSignIn }) {
  return (
    <Banner tone="warn" icon="⏳" actions={
      <button
        type="button"
        onClick={onSignIn}
        className="rounded-md border border-ink/15 bg-surface px-3 py-1 text-xs font-semibold hover:bg-paper"
      >
        Sign in again
      </button>
    }>
      <p className="text-sm font-medium">Your session expires soon.</p>
    </Banner>
  );
}

function HardError({ error, onRetry }) {
  const detail = error?.response?.data?.detail;
  return (
    <div className="tech-grid absolute inset-0 z-20 flex items-center justify-center bg-paper/80 p-6">
      <Card ticks className="max-w-md text-center animate-fade-up" padding={24} role="alert">
        <p className="font-display text-lg font-semibold tracking-tight">Couldn't load risk data</p>
        <p className="mt-2 text-sm text-ink-soft">
          {typeof detail === 'string'
            ? detail
            : 'The AquaSignal server is unreachable. Your network or the service may be down.'}
        </p>
        <Button className="mt-5" onClick={onRetry}>Try again</Button>
      </Card>
    </div>
  );
}
