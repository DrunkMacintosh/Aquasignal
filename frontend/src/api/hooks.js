// React Query hooks. Pattern: long gcTime + moderate staleTime gives
// stale-while-revalidate behaviour — cached data renders instantly while a
// background refetch runs; if the API is down the cache keeps the dashboard
// usable and the UI flags it as stale.
import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query';
import {
  fetchAdvisorConfig,
  fetchAlertHistory,
  fetchCellForecast,
  fetchCellHistory,
  fetchCellSatellite,
  fetchDistrictForecast,
  fetchDistrictHistory,
  fetchDistrictPermeability,
  fetchDistrictRiskMap,
  fetchDistrictSatellite,
  fetchRiskMap,
} from './client.js';
import { CRITICAL_THRESHOLD } from '../lib/risk.js';
import { useSubscriptions } from '../lib/subscriptions.js';

const MINUTE = 60_000;
const DAY = 24 * 60 * MINUTE;

export function useRiskMap(enabled = true) {
  return useQuery({
    queryKey: ['risk-map'],
    queryFn: fetchRiskMap,
    enabled, // the grid payload (~1400 cells) only loads when the grid view is shown
    staleTime: 5 * MINUTE,
    gcTime: DAY, // survive a full workday of API outage on cached data
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: true,
    retry: 1,
  });
}

export function useDistrictRiskMap() {
  return useQuery({
    queryKey: ['district-risk-map'],
    queryFn: fetchDistrictRiskMap,
    staleTime: 5 * MINUTE,
    gcTime: DAY,
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: true,
    retry: 1,
  });
}

export function useCellForecast(cellId) {
  return useQuery({
    queryKey: ['forecast', 'cell', cellId],
    queryFn: () => fetchCellForecast(cellId),
    enabled: Boolean(cellId),
    staleTime: 30 * MINUTE, // forecasts only change on the monthly model run
    gcTime: DAY,
  });
}

export function useDistrictForecast(districtName) {
  return useQuery({
    queryKey: ['forecast', 'district', districtName],
    queryFn: () => fetchDistrictForecast(districtName),
    enabled: Boolean(districtName),
    staleTime: 30 * MINUTE,
    gcTime: DAY,
  });
}

/**
 * 24-month observed history. Shared query key so the panel sparkline and the
 * alert banner reuse one fetch per district.
 */
function districtHistoryQuery(districtName) {
  return {
    queryKey: ['district-history', districtName],
    queryFn: async () => ({
      monthly: (await fetchDistrictHistory(districtName)).history,
    }),
    enabled: Boolean(districtName),
    staleTime: 30 * MINUTE,
    gcTime: DAY,
  };
}

export function useDistrictHistory(districtName) {
  return useQuery(districtHistoryQuery(districtName));
}

export function useCellHistory(cellId) {
  return useQuery({
    queryKey: ['history', 'cell', cellId],
    queryFn: () => fetchCellHistory(cellId),
    enabled: Boolean(cellId),
    staleTime: 30 * MINUTE,
    gcTime: DAY,
  });
}

export function useCellSatellite(cellId) {
  return useQuery({
    queryKey: ['satellite', 'cell', cellId],
    queryFn: () => fetchCellSatellite(cellId),
    enabled: Boolean(cellId),
    staleTime: 30 * MINUTE,
    gcTime: DAY,
  });
}

export function useDistrictSatellite(districtName) {
  return useQuery({
    queryKey: ['satellite', 'district', districtName],
    queryFn: () => fetchDistrictSatellite(districtName),
    enabled: Boolean(districtName),
    staleTime: 30 * MINUTE,
    gcTime: DAY,
  });
}

// Soil permeability is static and recharge only moves with the monthly
// pipeline, so it caches like the other monthly-cadence district reads.
export function useDistrictPermeability(districtName) {
  return useQuery({
    queryKey: ['permeability', 'district', districtName],
    queryFn: () => fetchDistrictPermeability(districtName),
    enabled: Boolean(districtName),
    staleTime: 30 * MINUTE,
    gcTime: DAY,
  });
}

// Advisor availability rarely changes within a session, so cache it for the
// day; the chat itself is a mutation, not a query.
export function useAdvisorConfig() {
  return useQuery({
    queryKey: ['advisor-config'],
    queryFn: fetchAdvisorConfig,
    staleTime: DAY,
    gcTime: DAY,
    retry: 1,
  });
}

export function useAlertHistory(districtName) {
  return useQuery({
    queryKey: ['alert-history', districtName],
    queryFn: () => fetchAlertHistory(districtName),
    enabled: Boolean(districtName),
    staleTime: 5 * MINUTE,
    gcTime: DAY,
  });
}

/**
 * Districts the user subscribed to whose latest district-average risk is in
 * the critical band. Drives the persistent alert banner.
 */
export function useCriticalDistricts() {
  const subscriptions = useSubscriptions();
  const districts = Object.keys(subscriptions).sort();
  const results = useQueries({
    queries: districts.map((district) => districtHistoryQuery(district)),
  });
  const critical = districts.filter((district, index) => {
    const monthly = results[index].data?.monthly;
    const latest = monthly?.[monthly.length - 1];
    return latest != null && latest.risk >= CRITICAL_THRESHOLD;
  });
  return { critical, isLoading: results.some((result) => result.isLoading) };
}
