// Single axios instance for the FastAPI backend. The JWT lives in module
// memory (set by AuthContext) — never in localStorage/sessionStorage — so an
// XSS payload cannot lift it from persistent storage.
import axios from 'axios';
import { getDeviceToken } from '../lib/deviceToken.js';
import { filenameFromDisposition } from '../lib/download.js';
import { markAwake, markWaking } from '../lib/warmup.js';

export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const api = axios.create({ baseURL: API_URL, timeout: 30_000 });

let accessToken = null;
let onUnauthorized = null;

export function setAccessToken(token) {
  accessToken = token;
}

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

// 502/503/504 (or no response at all) while the free-tier instance
// cold-starts: flag it so WarmupBanner can take over; any successful
// response clears the flag.
const GATEWAY_ERRORS = new Set([502, 503, 504]);

api.interceptors.response.use(
  (response) => {
    markAwake();
    return response;
  },
  (error) => {
    if (!error.response || GATEWAY_ERRORS.has(error.response.status)) {
      markWaking();
    }
    // Only treat 401 as "session died" when we *had* a token — a failed login
    // attempt must not bounce the user out of the login form.
    if (error.response?.status === 401 && accessToken && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  },
);

/** Unauthenticated liveness probe used by the warm-up banner. */
export function pingHealth() {
  return api.get('/health');
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password });
  return data; // { access_token, token_type, expires_in }
}

export async function register(email, password, fullName) {
  const { data } = await api.post('/auth/register', {
    email,
    password,
    full_name: fullName,
  });
  return data; // TokenResponse — the new account is signed in immediately
}

/** Exchanges the current (still valid) bearer token for a fresh 24 h one. */
export async function refreshToken() {
  const { data } = await api.post('/auth/refresh');
  return data;
}

// ---------------------------------------------------------------------------
// Risk map & forecasts
// ---------------------------------------------------------------------------

export async function fetchRiskMap() {
  const { data } = await api.get('/risk-map');
  return data; // GeoJSON FeatureCollection + month
}

export async function fetchDistrictRiskMap() {
  const { data } = await api.get('/risk-map/districts');
  return data; // GeoJSON FeatureCollection (district polygons) + month
}

export async function fetchCellForecast(cellId) {
  const { data } = await api.get(`/forecast/${encodeURIComponent(cellId)}`);
  return data;
}

export async function fetchDistrictForecast(districtName) {
  const { data } = await api.get(`/forecast/district/${encodeURIComponent(districtName)}`);
  return data;
}

// ---------------------------------------------------------------------------
// History & satellite observations
// ---------------------------------------------------------------------------

export async function fetchCellHistory(cellId) {
  const { data } = await api.get(`/history/${encodeURIComponent(cellId)}`);
  return data; // { cell_id, history: [{month, risk, risk_level}] }
}

export async function fetchDistrictHistory(districtName) {
  const { data } = await api.get(`/history/district/${encodeURIComponent(districtName)}`);
  return data; // { district_name, history: [...] }
}

export async function fetchCellSatellite(cellId, months = 24) {
  const { data } = await api.get(`/satellite/${encodeURIComponent(cellId)}`, {
    params: { months },
  });
  return data; // { cell_id, observations: [{month, grace_anomaly, ...}] }
}

export async function fetchDistrictSatellite(districtName, months = 24) {
  const { data } = await api.get(
    `/satellite/district/${encodeURIComponent(districtName)}`,
    { params: { months } },
  );
  return data;
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export async function fetchAlertHistory(districtName) {
  const { data } = await api.get(`/alerts/history/${encodeURIComponent(districtName)}`);
  return data;
}

export async function subscribeAlert(districtName, threshold) {
  const { data } = await api.post('/alerts/subscribe', {
    device_token: getDeviceToken(),
    district_name: districtName,
    threshold,
  });
  return data;
}

/** Removes this device's subscription for one district. */
export async function unsubscribeDistrict(districtName) {
  const { data } = await api.delete(
    `/alerts/subscribe/${encodeURIComponent(getDeviceToken())}/${encodeURIComponent(districtName)}`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

async function downloadExport(kind, districtName, fallbackExt) {
  const response = await api.get(`/export/${kind}/${encodeURIComponent(districtName)}`, {
    responseType: 'blob',
  });
  const fallback = `aquasignal_${districtName.replace(/\W+/g, '_')}.${fallbackExt}`;
  return {
    blob: response.data,
    filename: filenameFromDisposition(response.headers['content-disposition'], fallback),
  };
}

export function downloadCsvFile(districtName) {
  return downloadExport('csv', districtName, 'csv');
}

export function downloadPdfFile(districtName) {
  return downloadExport('pdf', districtName, 'pdf');
}
