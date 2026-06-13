// POST /alerts/subscribe expects an FCM device registration token. This web
// dashboard has no FCM integration yet, so each browser gets a stable random
// identifier instead. It is a device label, not a credential — persisting it
// in localStorage is fine (unlike the JWT, which stays in memory only).
const STORAGE_KEY = 'aquasignal.device-token';

export function getDeviceToken() {
  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing) return existing;
  const random =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const token = `web-${random}`;
  localStorage.setItem(STORAGE_KEY, token);
  return token;
}
