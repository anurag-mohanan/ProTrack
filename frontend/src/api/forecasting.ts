import type { FcCapacity, FcCatalog, FcEngineering, FcFinance, FcHorizonParams } from '../types/Forecasting';
import { apiClient, buildQuery } from './client';

export async function fetchForecastCatalog(): Promise<FcCatalog> {
  const { data } = await apiClient.get<FcCatalog>('/forecasts');
  return data;
}

export async function fetchEngineeringForecast(): Promise<FcEngineering> {
  const { data } = await apiClient.get<FcEngineering>('/forecasts/engineering');
  return data;
}

export async function fetchCapacityForecast(params: FcHorizonParams): Promise<FcCapacity> {
  const { data } = await apiClient.get<FcCapacity>(`/forecasts/capacity${buildQuery({ ...params })}`);
  return data;
}

export async function fetchFinanceForecast(params: FcHorizonParams): Promise<FcFinance> {
  const { data } = await apiClient.get<FcFinance>(`/forecasts/finance${buildQuery({ ...params })}`);
  return data;
}

export const forecastQueryKeys = {
  catalog: ['forecasts', 'catalog'] as const,
  engineering: ['forecasts', 'engineering'] as const,
  capacity: (params: FcHorizonParams) => ['forecasts', 'capacity', params] as const,
  finance: (params: FcHorizonParams) => ['forecasts', 'finance', params] as const,
};
