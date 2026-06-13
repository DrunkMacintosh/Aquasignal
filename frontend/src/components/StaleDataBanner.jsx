/**
 * Shown when the API is unreachable but React Query still holds cached data
 * (stale-while-revalidate): the dashboard keeps working on the last good
 * snapshot and says so honestly.
 */
export default function StaleDataBanner({ updatedAt, onRetry }) {
  const fetchedTime = updatedAt
    ? new Date(updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div
      role="status"
      className="pointer-events-auto flex flex-wrap items-center gap-3 rounded-xl border border-risk-medium/60 bg-[#FFF8E1] px-4 py-2.5 shadow-card animate-fade-up"
    >
      <span aria-hidden="true">⚠️</span>
      <p className="text-sm font-medium">
        Data unavailable — showing last cached data
        {fetchedTime && <span className="text-ink-soft"> (fetched {fetchedTime})</span>}
      </p>
      <button
        type="button"
        onClick={onRetry}
        aria-label="Retry loading latest data"
        className="ml-auto rounded-md border border-ink/15 bg-surface px-3 py-1 text-xs font-semibold hover:bg-paper"
      >
        Retry
      </button>
    </div>
  );
}
