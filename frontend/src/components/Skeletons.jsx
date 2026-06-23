// Loading placeholders. The map skeleton mimics the survey grid the real data
// draws so the loaded state doesn't visually "jump", with a cobalt scan sweep
// for an instrument "acquiring" feel.

export function MapSkeleton() {
  return (
    <div
      className="absolute inset-0 z-10 flex items-center justify-center overflow-hidden bg-paper"
      role="status"
      aria-label="Loading risk map"
    >
      <svg className="absolute inset-0 h-full w-full opacity-60" aria-hidden="true">
        <defs>
          <pattern id="survey-grid" width="52" height="52" patternUnits="userSpaceOnUse">
            <path d="M52 0H0V52" fill="none" stroke="#1F46E5" strokeOpacity="0.1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#survey-grid)" />
      </svg>
      {/* Sweeping acquisition band */}
      <div
        className="absolute inset-y-0 left-0 w-1/2 animate-scan bg-gradient-to-r from-transparent via-water/12 to-transparent"
        aria-hidden="true"
      />
      <div className="card corner-ticks flex items-center gap-3 px-5 py-3">
        <span className="h-2.5 w-2.5 animate-glow-pulse rounded-full bg-water" aria-hidden="true" />
        <span className="font-mono text-xs uppercase tracking-[0.2em] text-ink-soft">
          Acquiring survey grid…
        </span>
      </div>
    </div>
  );
}

export function PanelSkeleton() {
  return (
    <div className="space-y-4 p-5" role="status" aria-label="Loading details">
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
