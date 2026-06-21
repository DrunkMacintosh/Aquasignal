import Banner from './ui/Banner.jsx';

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
    <Banner tone="warn" icon="⚠️" actions={
      <button
        type="button"
        onClick={onRetry}
        aria-label="Retry loading latest data"
        className="rounded-md border border-ink/15 bg-surface px-3 py-1 text-xs font-semibold hover:bg-paper"
      >
        Retry
      </button>
    }>
      <p className="text-sm font-medium">
        Data unavailable — showing last cached data
        {fetchedTime && <span className="text-ink-soft"> (fetched {fetchedTime})</span>}
      </p>
    </Banner>
  );
}
