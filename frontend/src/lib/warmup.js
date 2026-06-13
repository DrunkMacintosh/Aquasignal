// Render's free tier spins the API down after 15 idle minutes; the first
// request then takes ~30 s while the instance boots. The axios interceptors
// flip this flag on gateway errors / dead connections and clear it on the
// first successful response, so the UI can say "warming up" instead of
// looking broken. Same useSyncExternalStore pattern as lib/subscriptions.js.
import { useSyncExternalStore } from 'react';

const listeners = new Set();
let isWaking = false;

function notify() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function markWaking() {
  if (!isWaking) {
    isWaking = true;
    notify();
  }
}

export function markAwake() {
  if (isWaking) {
    isWaking = false;
    notify();
  }
}

export function useServiceWaking() {
  return useSyncExternalStore(subscribe, () => isWaking);
}
