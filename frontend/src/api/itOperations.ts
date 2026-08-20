import { apiClient, buildQuery, type ListParams } from './client';
import {
  normalizePaginatedResponse,
  unwrapListResponse,
  type PaginatedResponse,
} from '../types/pagination';
import type {
  AssetAssignPayload,
  AssetAssignment,
  AssetReturnPayload,
  AssetTransferPayload,
  AssetType,
  AssetTypeCreate,
  AssetTypeUpdate,
  IpAllocatePayload,
  IpReleasePayload,
  ITAsset,
  ITAssetCreate,
  ITAssetUpdate,
  AssetCustomerReturn,
  CustomerAssetReturnReportRow,
  ITComputer,
  ITComputerCreate,
  ITComputerUpdate,
  ITDashboardSummary,
  ITIpAddress,
  ITNetwork,
  ITNetworkCreate,
  ITNetworkUpdate,
  ITOpenRequest,
  ITOnboardingTask,
  ITProfile,
  ITSettings,
  ITSettingsUpdate,
} from '../types/itOperations';

export const itOperationsKeys = {
  all: ['it'] as const,
  dashboard: () => [...itOperationsKeys.all, 'dashboard'] as const,
  onboardingTasks: () => [...itOperationsKeys.all, 'dashboard', 'onboarding-tasks'] as const,
  assetTypes: () => [...itOperationsKeys.all, 'asset-types'] as const,
  assets: (filters?: ListParams) => [...itOperationsKeys.all, 'assets', filters ?? {}] as const,
  asset: (id: string) => [...itOperationsKeys.all, 'assets', id] as const,
  customerReturns: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'customer-returns', filters ?? {}] as const,
  customerReturnsReport: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'reports', 'customer-returns', filters ?? {}] as const,
  assetAssignments: (id: string) =>
    [...itOperationsKeys.all, 'assets', id, 'assignments'] as const,
  computers: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'computers', filters ?? {}] as const,
  computer: (id: string) => [...itOperationsKeys.all, 'computers', id] as const,
  networks: () => [...itOperationsKeys.all, 'networks'] as const,
  network: (id: string) => [...itOperationsKeys.all, 'networks', id] as const,
  networkIps: (id: string, status?: string) =>
    [...itOperationsKeys.all, 'networks', id, 'ips', status ?? 'all'] as const,
  settings: () => [...itOperationsKeys.all, 'settings'] as const,
  profileMe: () => [...itOperationsKeys.all, 'profile', 'me'] as const,
  profileUser: (userId: string) => [...itOperationsKeys.all, 'profile', userId] as const,
  openRequests: () => [...itOperationsKeys.all, 'reports', 'open-requests'] as const,
};

async function getListOrPage<T>(path: string, params?: ListParams): Promise<PaginatedResponse<T>> {
  const { data } = await apiClient.get<unknown>(`${path}${buildQuery(params)}`);
  return normalizePaginatedResponse<T>(data);
}

async function getList<T>(path: string, params?: ListParams): Promise<T[]> {
  const { data } = await apiClient.get<unknown>(`${path}${buildQuery(params)}`);
  return unwrapListResponse<T>(data);
}

// --- Dashboard ---

export async function fetchItDashboard(): Promise<ITDashboardSummary> {
  const { data } = await apiClient.get<ITDashboardSummary>('/it/dashboard');
  return data;
}

// --- Asset types ---

export async function fetchAssetTypes(): Promise<AssetType[]> {
  return getList<AssetType>('/it/asset-types');
}

export async function createAssetType(payload: AssetTypeCreate): Promise<AssetType> {
  const { data } = await apiClient.post<AssetType>('/it/asset-types', payload);
  return data;
}

export async function updateAssetType(id: string, payload: AssetTypeUpdate): Promise<AssetType> {
  const { data } = await apiClient.patch<AssetType>(`/it/asset-types/${id}`, payload);
  return data;
}

// --- Assets ---

export async function fetchAssetsPaginated(
  params?: ListParams,
): Promise<PaginatedResponse<ITAsset>> {
  return getListOrPage<ITAsset>('/it/assets', params);
}

export async function fetchAssets(params?: ListParams): Promise<ITAsset[]> {
  return getList<ITAsset>('/it/assets', params);
}

export async function fetchAsset(id: string): Promise<ITAsset> {
  const { data } = await apiClient.get<ITAsset>(`/it/assets/${id}`);
  return data;
}

export async function createAsset(payload: ITAssetCreate): Promise<ITAsset> {
  const { data } = await apiClient.post<ITAsset>('/it/assets', payload);
  return data;
}

export async function updateAsset(id: string, payload: ITAssetUpdate): Promise<ITAsset> {
  const { data } = await apiClient.patch<ITAsset>(`/it/assets/${id}`, payload);
  return data;
}

export async function deleteAsset(id: string): Promise<void> {
  await apiClient.delete(`/it/assets/${id}`);
}

export async function assignAsset(id: string, payload: AssetAssignPayload): Promise<ITAsset> {
  const { data } = await apiClient.post<ITAsset>(`/it/assets/${id}/assign`, payload);
  return data;
}

export async function returnAsset(id: string, payload: AssetReturnPayload = {}): Promise<ITAsset> {
  const { data } = await apiClient.post<ITAsset>(`/it/assets/${id}/return`, payload);
  return data;
}

export async function returnAssetToCustomer(
  id: string,
  payload: {
    return_date?: string | null;
    owner_customer_id?: string | null;
    received_by_name?: string | null;
    condition_at_return?: string | null;
    return_reason?: string | null;
    notes?: string | null;
  } = {},
): Promise<AssetCustomerReturn> {
  const { data } = await apiClient.post<AssetCustomerReturn>(
    `/it/assets/${id}/return-to-customer`,
    payload,
  );
  return data;
}

export async function fetchCustomerReturns(
  params?: ListParams & { owner_customer_id?: string },
): Promise<AssetCustomerReturn[]> {
  return getList<AssetCustomerReturn>('/it/assets/customer-returns', params);
}

export async function fetchCustomerReturnsReport(
  params?: ListParams & { owner_customer_id?: string },
): Promise<CustomerAssetReturnReportRow[]> {
  return getList<CustomerAssetReturnReportRow>('/it/reports/customer-returns', params);
}

export async function transferAsset(id: string, payload: AssetTransferPayload): Promise<ITAsset> {
  const { data } = await apiClient.post<ITAsset>(`/it/assets/${id}/transfer`, payload);
  return data;
}

export async function fetchAssetAssignments(id: string): Promise<AssetAssignment[]> {
  return getList<AssetAssignment>(`/it/assets/${id}/assignments`);
}

// --- Computers ---

export async function fetchComputersPaginated(
  params?: ListParams,
): Promise<PaginatedResponse<ITComputer>> {
  return getListOrPage<ITComputer>('/it/computers', params);
}

export async function fetchComputer(id: string): Promise<ITComputer> {
  const { data } = await apiClient.get<ITComputer>(`/it/computers/${id}`);
  return data;
}

export async function createComputer(payload: ITComputerCreate): Promise<ITComputer> {
  const { data } = await apiClient.post<ITComputer>('/it/computers', payload);
  return data;
}

export async function updateComputer(id: string, payload: ITComputerUpdate): Promise<ITComputer> {
  const { data } = await apiClient.patch<ITComputer>(`/it/computers/${id}`, payload);
  return data;
}

// --- Networks & IPs ---

export async function fetchNetworks(): Promise<ITNetwork[]> {
  return getList<ITNetwork>('/it/networks');
}

export async function fetchNetwork(id: string): Promise<ITNetwork> {
  const { data } = await apiClient.get<ITNetwork>(`/it/networks/${id}`);
  return data;
}

export async function createNetwork(payload: ITNetworkCreate): Promise<ITNetwork> {
  const { data } = await apiClient.post<ITNetwork>('/it/networks', payload);
  return data;
}

export async function updateNetwork(id: string, payload: ITNetworkUpdate): Promise<ITNetwork> {
  const { data } = await apiClient.patch<ITNetwork>(`/it/networks/${id}`, payload);
  return data;
}

export async function fetchNetworkIps(
  networkId: string,
  params?: { status?: string },
): Promise<ITIpAddress[]> {
  return getList<ITIpAddress>(`/it/networks/${networkId}/ips`, params);
}

export async function allocateIp(payload: IpAllocatePayload): Promise<ITIpAddress> {
  const { data } = await apiClient.post<ITIpAddress>('/it/ips/allocate', payload);
  return data;
}

export async function releaseIp(id: string, payload: IpReleasePayload = {}): Promise<ITIpAddress> {
  const { data } = await apiClient.post<ITIpAddress>(`/it/ips/${id}/release`, payload);
  return data;
}

// --- Settings / profile / reports ---

export async function fetchItSettings(): Promise<ITSettings> {
  const { data } = await apiClient.get<ITSettings>('/it/settings');
  return data;
}

export async function updateItSettings(payload: ITSettingsUpdate): Promise<ITSettings> {
  const { data } = await apiClient.put<ITSettings>('/it/settings', payload);
  return data;
}

export interface ITMigrationSourceType {
  id: string;
  label: string;
  sheet_hint: string;
  description: string;
}

export interface ITMigrationAnalyzeResult {
  session_id: string;
  source_type: string;
  filename: string;
  sheet_name: string;
  workbook_format?: string;
  column_bindings?: Record<string, string | null>;
  records_found: number;
  new_records: number;
  potential_duplicates: number;
  skipped_records: number;
  requires_review: number;
  warning_count?: number;
  error_count?: number;
  sensitive_columns_excluded: string[];
  sensitive_data_excluded_count: number;
  headers: string[];
  duplicates: Array<Record<string, unknown>>;
  exceptions: Array<Record<string, unknown>>;
  preview_rows: Array<Record<string, string>>;
  first_five_mapped?: Array<Record<string, string>>;
  confirm_required: boolean;
  message: string;
}

export interface ITMigrationImportResult {
  session_id: string;
  source_type: string;
  filename?: string | null;
  imported: number;
  skipped: number;
  duplicated: number;
  conflicted: number;
  requires_review: number;
  sensitive_data_excluded: number;
  organization_owned: number;
  customer_owned: number;
  returned_assets: number;
  errors: string[];
  message: string;
}

export async function fetchMigrationSourceTypes(): Promise<ITMigrationSourceType[]> {
  const { data } = await apiClient.get<ITMigrationSourceType[]>('/it/migration/source-types');
  return data;
}

export async function analyzeItMigration(
  sourceType: string,
  file: File,
): Promise<ITMigrationAnalyzeResult> {
  const form = new FormData();
  form.append('source_type', sourceType);
  form.append('file', file);
  const { data } = await apiClient.post<ITMigrationAnalyzeResult>('/it/migration/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function commitItMigration(payload: {
  session_id: string;
  confirm: boolean;
  skip_duplicates?: boolean;
  skip_review_rows?: boolean;
}): Promise<ITMigrationImportResult> {
  const form = new FormData();
  form.append('session_id', payload.session_id);
  form.append('confirm', String(payload.confirm));
  form.append('skip_duplicates', String(payload.skip_duplicates ?? true));
  form.append('skip_review_rows', String(payload.skip_review_rows ?? false));
  const { data } = await apiClient.post<ITMigrationImportResult>('/it/migration/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function fetchMyItProfile(): Promise<ITProfile> {
  const { data } = await apiClient.get<ITProfile>('/it/profile/me');
  return data;
}

export async function fetchUserItProfile(userId: string): Promise<ITProfile> {
  const { data } = await apiClient.get<ITProfile>(`/it/profile/${userId}`);
  return data;
}

export async function fetchItOnboardingTasks(): Promise<ITOnboardingTask[]> {
  return getList<ITOnboardingTask>('/it/dashboard/onboarding-tasks');
}

export async function fetchOpenItRequests(): Promise<ITOpenRequest[]> {
  return getList<ITOpenRequest>('/it/reports/open-requests');
}
