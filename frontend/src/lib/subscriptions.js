// The backend stores alert subscriptions but exposes no "list mine" endpoint,
// so the dashboard mirrors them locally (district -> threshold). District
// names and thresholds are not sensitive, so localStorage is acceptable here.
// A tiny external store (useSyncExternalStore) lets the alert banner and the
// panel toggle share one source of truth without prop drilling.
import { useSyncExternalStore } from 'react';

const STORAGE_KEY = 'aquasignal.subscriptions';
const listeners = new Set();

function readStorage() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

let snapshot = readStorage();

function commit(next) {
  snapshot = next;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSubscriptions() {
  return snapshot;
}

export function setSubscription(district, threshold) {
  commit({ ...snapshot, [district]: threshold });
}

export function removeSubscription(district) {
  const { [district]: _removed, ...rest } = snapshot;
  commit(rest);
}

export function useSubscriptions() {
  return useSyncExternalStore(subscribe, getSubscriptions);
}
