// Shown while the free-tier API instance cold-starts (~30 s). Polls /health
// every 5 s; the success interceptor in api/client.js clears the flag, after
// which every cached query refetches so the screen heals without a reload.
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { pingHealth } from '../api/client.js';
import { useServiceWaking } from '../lib/warmup.js';

const RETRY_INTERVAL_MS = 5_000;

export default function WarmupBanner() {
  const isWaking = useServiceWaking();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isWaking) return undefined;
    // Recursive setTimeout, not setInterval: a cold-starting /health call can
    // take longer than the interval, and overlapping polls would stack.
    let timer;
    let cancelled = false;
    const poll = async () => {
      try {
        await pingHealth(); // success flips the store via the interceptor
        queryClient.invalidateQueries();
      } catch {
        // still asleep — keep waiting
      }
      if (!cancelled) timer = setTimeout(poll, RETRY_INTERVAL_MS);
    };
    timer = setTimeout(poll, RETRY_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [isWaking, queryClient]);

  if (!isWaking) return null;

  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-3 bg-ink px-4 py-2.5 text-white"
    >
      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" aria-hidden="true" />
      <p className="text-sm font-medium">
        Connecting to the service… on free hosting the first load can take about 30
        seconds. Retrying automatically.
      </p>
    </div>
  );
}
