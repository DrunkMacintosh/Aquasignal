// Loading placeholders. The map skeleton mimics the survey-grid the real data
// draws so the loaded state doesn't visually "jump".

export function MapSkeleton() {
  return (
    <div
      className="absolute inset-0 z-10 flex items-center justify-center bg-paper"
      role="status"
      aria-label="Loading risk map"
    >
      <svg className="absolute inset-0 h-full w-full opacity-[0.35]" aria-hidden="true">
        <defs>
          <pattern id="survey-grid" width="56" height="56" patternUnits="userSpaceOnUse">
            <path d="M56 0H0V56" fill="none" stroke="#1C2B33" strokeOpacity="0.12" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#survey-grid)" />
      </svg>
      <div className="card flex items-center gap-3 px-5 py-3">
        <span className="h-3 w-3 animate-pulse rounded-full bg-water" aria-hidden="true" />
        <span className="font-mono text-xs uppercase tracking-[0.18em] text-ink-soft">
          Loading survey grid…
        </span>
      </div>
    </div>
  );
}

export function PanelSkeleton() {
  return (
    <div className="space-y-4 p-5" role="status" aria-label="Loading district details">
      <div className="skeleton h-7 w-2/3" />
      <div className="skeleton h-24 w-full" />
      <div className="skeleton h-5 w-1/3" />
      <div className="skeleton h-48 w-full" />
      <div className="skeleton h-5 w-1/2" />
      <div className="skeleton h-14 w-full" />
    </div>
  );
}

export function ChartSkeleton({ height = 220 }) {
  return <div className="skeleton w-full" style={{ height }} role="status" aria-label="Loading chart" />;
}
