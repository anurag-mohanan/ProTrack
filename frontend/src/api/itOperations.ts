import { apiClient, buildQuery, type ListParams } from './client';
import {
  normalizePaginatedResponse,
  unwrapListResponse,
  type PaginatedResponse,
} from '../types/pagination';
import type {
  AssetAssignPayload,
  AssetAssignment,
  AssetBulkActionRequest,
  AssetBulkActionResult,
  AssetBulkIdsResponse,
  AssetBulkPreviewResponse,
  AssetReturnPayload,
  AssetTransferPayload,
  AssetType,
  AssetTypeCreate,
  AssetTypeUpdate,
  AssetMake,
  AssetMakeCreate,
  AssetModel,
  AssetModelCreate,
  IpAllocatePayload,
  IpReleasePayload,
  IPAssignmentHistory,
  ITAsset,
  ITAssetCategory,
  ITAssetCreate,
  ITAssetUpdate,
  AssetCustomerReturn,
  CustomerAssetReturnReportRow,
  ITComputer,
  ITComputerCreate,
  ITComputerUpdate,
  ComputerNetworkInterface,
  ComputerNetworkInterfacePayload,
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
  ITSupplier,
  ITSupplierCreate,
  MasterKind,
  MasterMergeResult,
  NextAssetNumberPreview,
  NextAssetNumbersPreview,
  SoftwareAssignment,
  SoftwareAssignmentCreate,
  SoftwareInstallation,
  SoftwareCatalogCreate,
  SoftwareCatalogItem,
  SoftwareCatalogUpdate,
  SoftwareCompliance,
  SoftwareExpirySummary,
  SoftwareLicensePool,
  SoftwareLicensePoolCreate,
  SoftwareLicensePoolUpdate,
  EmployeeSoftwareRequirement,
  EmployeeSoftwareRequirementCreate,
  EmployeeSoftwareRequirementUpdate,
  ResourcePackage,
  ResourcePackagePreview,
  ResourcePackageUpsert,
} from '../types/itOperations';

export const itOperationsKeys = {
  all: ['it'] as const,
  dashboard: () => [...itOperationsKeys.all, 'dashboard'] as const,
  onboardingTasks: () => [...itOperationsKeys.all, 'dashboard', 'onboarding-tasks'] as const,
  assetTypes: () => [...itOperationsKeys.all, 'asset-types'] as const,
  masterCategories: () => [...itOperationsKeys.all, 'master', 'categories'] as const,
  masterTypes: (category?: string) =>
    [...itOperationsKeys.all, 'master', 'types', category ?? 'all'] as const,
  masterMakes: (assetTypeId?: string) =>
    [...itOperationsKeys.all, 'master', 'makes', assetTypeId ?? 'all'] as const,
  masterModels: (makeId?: string, assetTypeId?: string) =>
    [...itOperationsKeys.all, 'master', 'models', makeId ?? 'all', assetTypeId ?? 'all'] as const,
  masterSuppliers: (search?: string) =>
    [...itOperationsKeys.all, 'master', 'suppliers', search ?? ''] as const,
  nextAssetNumber: (assetTypeId: string) =>
    [...itOperationsKeys.all, 'assets', 'next-number', assetTypeId] as const,
  assets: (filters?: ListParams) => [...itOperationsKeys.all, 'assets', filters ?? {}] as const,
  asset: (id: string) => [...itOperationsKeys.all, 'assets', id] as const,
  customerReturns: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'customer-returns', filters ?? {}] as const,
  customerReturnsReport: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'reports', 'customer-returns', filters ?? {}] as const,
  assetAssignments: (id: string) =>
    [...itOperationsKeys.all, 'assets', id, 'assignments'] as const,
  assetChildren: (id: string) =>
    [...itOperationsKeys.all, 'assets', id, 'children'] as const,
  assetIpHistory: (id: string) =>
    [...itOperationsKeys.all, 'assets', id, 'ip-history'] as const,
  assetLifecycleHistory: (id: string) =>
    [...itOperationsKeys.all, 'assets', id, 'lifecycle-history'] as const,
  computers: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'computers', filters ?? {}] as const,
  computer: (id: string) => [...itOperationsKeys.all, 'computers', id] as const,
  computerInterfaces: (id: string) =>
    [...itOperationsKeys.all, 'computers', id, 'interfaces'] as const,
  people: (filters?: ListParams) => [...itOperationsKeys.all, 'people', filters ?? {}] as const,
  person: (id: string) => [...itOperationsKeys.all, 'people', id] as const,
  resetPreview: () => [...itOperationsKeys.all, 'reset-preview'] as const,
  networks: () => [...itOperationsKeys.all, 'networks'] as const,
  network: (id: string) => [...itOperationsKeys.all, 'networks', id] as const,
  networkIps: (id: string, status?: string) =>
    [...itOperationsKeys.all, 'networks', id, 'ips', status ?? 'all'] as const,
  ipHistory: (id: string) => [...itOperationsKeys.all, 'ips', id, 'history'] as const,
  settings: () => [...itOperationsKeys.all, 'settings'] as const,
  profileMe: () => [...itOperationsKeys.all, 'profile', 'me'] as const,
  profileUser: (userId: string) => [...itOperationsKeys.all, 'profile', userId] as const,
  openRequests: () => [...itOperationsKeys.all, 'reports', 'open-requests'] as const,
  software: (filters?: ListParams) => [...itOperationsKeys.all, 'software', filters ?? {}] as const,
  softwareLicenses: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'software-licenses', filters ?? {}] as const,
  softwareAssignments: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'software-assignments', filters ?? {}] as const,
  softwareInstallations: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'software-installations', filters ?? {}] as const,
  softwareRequirements: (filters?: ListParams) =>
    [...itOperationsKeys.all, 'software-requirements', filters ?? {}] as const,
  softwareExpiry: () => [...itOperationsKeys.all, 'software-expiry'] as const,
  softwareCompliance: (userId: string) =>
    [...itOperationsKeys.all, 'software-compliance', userId] as const,
  resourcePackages: (activeOnly?: boolean) =>
    [...itOperationsKeys.all, 'resource-packages', activeOnly ? 'active' : 'all'] as const,
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

// --- Cascading master data ---

export async function fetchMasterCategories(params?: {
  active_only?: boolean;
}): Promise<ITAssetCategory[]> {
  return getList<ITAssetCategory>('/it/master/categories', params);
}

export async function createMasterCategory(payload: {
  name: string;
  code?: string;
}): Promise<ITAssetCategory> {
  const { data } = await apiClient.post<ITAssetCategory>('/it/master/categories', payload);
  return data;
}

export async function fetchMasterTypes(params?: {
  category?: string;
  active_only?: boolean;
}): Promise<AssetType[]> {
  return getList<AssetType>('/it/master/types', params);
}

export async function fetchMasterMakes(params?: {
  asset_type_id?: string;
  active_only?: boolean;
}): Promise<AssetMake[]> {
  return getList<AssetMake>('/it/master/makes', params);
}

export async function createMasterMake(payload: AssetMakeCreate): Promise<AssetMake> {
  const { data } = await apiClient.post<AssetMake>('/it/master/makes', payload);
  return data;
}

export async function fetchMasterModels(params?: {
  make_id?: string;
  asset_type_id?: string;
  active_only?: boolean;
}): Promise<AssetModel[]> {
  return getList<AssetModel>('/it/master/models', params);
}

export async function createMasterModel(payload: AssetModelCreate): Promise<AssetModel> {
  const { data } = await apiClient.post<AssetModel>('/it/master/models', payload);
  return data;
}

export async function fetchMasterSuppliers(params?: {
  active_only?: boolean;
  search?: string;
}): Promise<ITSupplier[]> {
  return getList<ITSupplier>('/it/master/suppliers', params);
}

export async function createMasterSupplier(payload: ITSupplierCreate): Promise<ITSupplier> {
  const { data } = await apiClient.post<ITSupplier>('/it/master/suppliers', payload);
  return data;
}

export async function setMasterActive(
  kind: MasterKind,
  id: string,
  isActive: boolean,
): Promise<ITAssetCategory | AssetType | AssetMake | AssetModel | ITSupplier> {
  const { data } = await apiClient.patch(`/it/master/${kind}/${id}/active`, {
    is_active: isActive,
  });
  return data;
}

export async function mergeMasterMake(
  sourceId: string,
  targetMakeId: string,
): Promise<MasterMergeResult> {
  const { data } = await apiClient.post<MasterMergeResult>(
    `/it/master/makes/${sourceId}/merge`,
    { target_make_id: targetMakeId },
  );
  return data;
}

export async function mergeMasterModel(
  sourceId: string,
  targetModelId: string,
): Promise<MasterMergeResult> {
  const { data } = await apiClient.post<MasterMergeResult>(
    `/it/master/models/${sourceId}/merge`,
    { target_model_id: targetModelId },
  );
  return data;
}

export async function fetchNextAssetNumber(assetTypeId: string): Promise<NextAssetNumberPreview> {
  const { data } = await apiClient.get<NextAssetNumberPreview>(
    `/it/assets/next-number${buildQuery({ asset_type_id: assetTypeId })}`,
  );
  return data;
}

export async function fetchNextAssetNumbers(
  assetTypeId: string,
  count: number,
): Promise<NextAssetNumbersPreview> {
  const { data } = await apiClient.get<NextAssetNumbersPreview>(
    `/it/assets/next-numbers${buildQuery({ asset_type_id: assetTypeId, count })}`,
  );
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

export async function fetchAssetIds(params?: ListParams): Promise<AssetBulkIdsResponse> {
  const { data } = await apiClient.get<AssetBulkIdsResponse>(`/it/assets/ids${buildQuery(params)}`);
  return data;
}

export async function previewAssetBulkAction(
  payload: AssetBulkActionRequest,
): Promise<AssetBulkPreviewResponse> {
  const { data } = await apiClient.post<AssetBulkPreviewResponse>('/it/assets/bulk-preview', {
    asset_ids: payload.asset_ids,
    action: payload.action,
    parameters: payload.parameters ?? {},
  });
  return data;
}

export async function executeAssetBulkAction(
  payload: AssetBulkActionRequest,
): Promise<AssetBulkActionResult> {
  const { data } = await apiClient.post<AssetBulkActionResult>('/it/assets/bulk-action', {
    asset_ids: payload.asset_ids,
    action: payload.action,
    parameters: payload.parameters ?? {},
    options: payload.options ?? {},
  });
  return data;
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

export async function fetchAssetChildren(id: string): Promise<ITAsset[]> {
  return getList<ITAsset>(`/it/assets/${id}/children`);
}

export async function returnAssetsForPerson(
  userId: string,
  payload: AssetReturnPayload = {},
): Promise<AssetAssignment[]> {
  const { data } = await apiClient.post<AssetAssignment[]>(
    `/it/people/${userId}/return-assets`,
    payload,
  );
  return data;
}

export async function fetchAssetAssignments(id: string): Promise<AssetAssignment[]> {
  return getList<AssetAssignment>(`/it/assets/${id}/assignments`);
}

export async function fetchAssetIpHistory(id: string): Promise<IPAssignmentHistory[]> {
  return getList<IPAssignmentHistory>(`/it/assets/${id}/ip-history`);
}

export type AssetLifecycleHistory = {
  ownership: Array<Record<string, unknown>>;
  locations: Array<Record<string, unknown>>;
  statuses: Array<Record<string, unknown>>;
  asset_numbers?: Array<Record<string, unknown>>;
};

export async function fetchAssetLifecycleHistory(id: string): Promise<AssetLifecycleHistory> {
  const { data } = await apiClient.get<AssetLifecycleHistory>(
    `/it/assets/${id}/lifecycle-history`,
  );
  return data;
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

export async function fetchComputerInterfaces(
  computerId: string,
): Promise<ComputerNetworkInterface[]> {
  return getList<ComputerNetworkInterface>(`/it/computers/${computerId}/interfaces`);
}

export async function createComputerInterface(
  computerId: string,
  payload: ComputerNetworkInterfacePayload,
): Promise<ComputerNetworkInterface> {
  const { data } = await apiClient.post<ComputerNetworkInterface>(
    `/it/computers/${computerId}/interfaces`,
    payload,
  );
  return data;
}

export async function updateComputerInterface(
  computerId: string,
  interfaceId: string,
  payload: Partial<ComputerNetworkInterfacePayload>,
): Promise<ComputerNetworkInterface> {
  const { data } = await apiClient.patch<ComputerNetworkInterface>(
    `/it/computers/${computerId}/interfaces/${interfaceId}`,
    payload,
  );
  return data;
}

export async function deleteComputerInterface(
  computerId: string,
  interfaceId: string,
): Promise<void> {
  await apiClient.delete(`/it/computers/${computerId}/interfaces/${interfaceId}`);
}

export async function assignComputer(
  id: string,
  payload: { user_id: string; assigned_date?: string | null; notes?: string | null },
): Promise<unknown> {
  const { data } = await apiClient.post(`/it/computers/${id}/assign`, payload);
  return data;
}

export async function unassignComputer(
  id: string,
  payload?: { reason?: string | null; notes?: string | null },
): Promise<unknown> {
  const { data } = await apiClient.post(`/it/computers/${id}/unassign`, payload ?? {});
  return data;
}

export async function transferComputer(
  id: string,
  payload: { to_user_id: string; reason?: string | null; notes?: string | null },
): Promise<unknown> {
  const { data } = await apiClient.post(`/it/computers/${id}/transfer`, payload);
  return data;
}

export async function fetchComputerDataQuality(): Promise<{
  computers_total: number;
  assigned_without_employee: number;
  available_with_open_assignment: number;
  computers_without_location: number;
  computers_without_ram: number;
  assigned_without_team: number;
  employees_without_computer: number;
  employees_without_shift_today: number;
  samples: Record<string, unknown[]>;
}> {
  const { data } = await apiClient.get('/it/computers/data-quality');
  return data;
}

export async function fetchItDataQuality(): Promise<
  import('./resourcePlanning').DataQualityReport
> {
  const { data } = await apiClient.get('/it/data-quality');
  return data;
}

export async function reconcileOrphanAssignedComputers(): Promise<{
  repaired_count: number;
  repaired: Array<Record<string, string>>;
}> {
  const { data } = await apiClient.post('/it/computers/reconcile-orphan-assigned');
  return data;
}

export async function fetchItPeoplePaginated(
  params?: ListParams & { status?: string },
): Promise<PaginatedResponse<import('../types/itOperations').ITPersonListItem>> {
  return getListOrPage('/it/people', params);
}

export async function fetchItPerson(
  userId: string,
): Promise<import('../types/itOperations').ITPersonDetail> {
  const { data } = await apiClient.get(`/it/people/${userId}`);
  return data;
}

export async function fetchItResetPreview(): Promise<import('../types/itOperations').ITResetPreview> {
  const { data } = await apiClient.get('/it/data-management/reset-preview');
  return data;
}

export async function executeItReset(payload: {
  confirmation_phrase: string;
  confirm: boolean;
}): Promise<import('../types/itOperations').ITResetResult> {
  const form = new FormData();
  form.append('confirmation_phrase', payload.confirmation_phrase);
  form.append('confirm', String(payload.confirm));
  const { data } = await apiClient.post('/it/data-management/reset', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
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

export async function fetchIpHistory(id: string): Promise<IPAssignmentHistory[]> {
  return getList<IPAssignmentHistory>(`/it/ips/${id}/history`);
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

// ---------------------------------------------------------------------------
// Sequential IT Data Import
// ---------------------------------------------------------------------------

export interface ITDataImportTypeStatus {
  id: string;
  label: string;
  expected_filename: string;
  recommended_order: number;
  depends_on: string[];
  review_only: boolean;
  canonical_sheet: string;
  accepted_sheets?: string[];
  status: string;
  latest_batch_id: string | null;
  latest_batch_code: string | null;
  latest_committed_at: string | null;
  success_count: number;
}

export interface ITImportBatchRead {
  id: string;
  batch_code: string;
  import_type: string;
  filename: string;
  sheet_name: string | null;
  uploaded_by_user_id: string;
  status: string;
  record_count: number;
  success_count: number;
  skipped_count: number;
  error_count: number;
  warning_count: number;
  session_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ITDataImportAnalyzeResult {
  batch_id: string;
  batch_code: string;
  session_id: string;
  import_type: string;
  requested_import_type?: string;
  processing_type?: string;
  filename: string;
  sheet_name: string;
  other_sheets: string[];
  canonical_sheet: string;
  sheet_detection?: Record<string, unknown>;
  review_only: boolean;
  headers: string[];
  column_bindings: Record<string, string | null>;
  unmapped_columns: string[];
  sensitive_columns_excluded: string[];
  stats: Record<string, number>;
  first_10_records: Record<string, unknown>[];
  dependency_warnings: string[];
  fidelity_note: string | null;
  block_commit: boolean;
  commit_allowed: boolean;
  confirm_required: boolean;
  message: string;
}

export interface ITDataImportCommitResult {
  batch_id: string;
  batch_code: string;
  import_type: string;
  filename?: string | null;
  status: string;
  imported: number;
  skipped: number;
  duplicated: number;
  errors: string[];
  deleted?: Record<string, number>;
  message: string;
}

export async function fetchItDataImportTypes(): Promise<ITDataImportTypeStatus[]> {
  const { data } = await apiClient.get<ITDataImportTypeStatus[]>('/it/data-import/types');
  return data;
}

export async function fetchItDataImportBatches(params?: {
  import_type?: string;
  status?: string;
}): Promise<ITImportBatchRead[]> {
  const { data } = await apiClient.get<ITImportBatchRead[]>('/it/data-import/batches', {
    params,
  });
  return data;
}

export async function analyzeItDataImport(
  importType: string,
  file: File,
  sheetName?: string | null,
): Promise<ITDataImportAnalyzeResult> {
  const form = new FormData();
  form.append('import_type', importType);
  form.append('file', file);
  if (sheetName) form.append('sheet_name', sheetName);
  const { data } = await apiClient.post<ITDataImportAnalyzeResult>('/it/data-import/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function commitItDataImport(payload: {
  batch_id: string;
  confirm: boolean;
  skip_duplicates?: boolean;
}): Promise<ITDataImportCommitResult> {
  const form = new FormData();
  form.append('batch_id', payload.batch_id);
  form.append('confirm', String(payload.confirm));
  form.append('skip_duplicates', String(payload.skip_duplicates ?? true));
  const { data } = await apiClient.post<ITDataImportCommitResult>('/it/data-import/commit', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function rollbackItDataImport(payload: {
  batch_id: string;
  confirm: boolean;
}): Promise<ITDataImportCommitResult> {
  const form = new FormData();
  form.append('batch_id', payload.batch_id);
  form.append('confirm', String(payload.confirm));
  const { data } = await apiClient.post<ITDataImportCommitResult>(
    '/it/data-import/rollback',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
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

export async function fetchResourcePackages(activeOnly = false): Promise<ResourcePackage[]> {
  return getList<ResourcePackage>('/it/resource-packages', { active_only: activeOnly });
}

export async function createResourcePackage(payload: ResourcePackageUpsert): Promise<ResourcePackage> {
  const { data } = await apiClient.post<ResourcePackage>('/it/resource-packages', payload);
  return data;
}

export async function updateResourcePackage(
  id: string,
  payload: Partial<ResourcePackageUpsert>,
): Promise<ResourcePackage> {
  const { data } = await apiClient.patch<ResourcePackage>(`/it/resource-packages/${id}`, payload);
  return data;
}

export async function deactivateResourcePackage(id: string): Promise<ResourcePackage> {
  const { data } = await apiClient.delete<ResourcePackage>(`/it/resource-packages/${id}`);
  return data;
}

export async function fetchItOnboardingTasks(): Promise<ITOnboardingTask[]> {
  return getList<ITOnboardingTask>('/it/dashboard/onboarding-tasks');
}

export async function fetchOpenItRequests(): Promise<ITOpenRequest[]> {
  return getList<ITOpenRequest>('/it/reports/open-requests');
}

// --- Software & licenses ---

export async function fetchSoftwareCatalog(params?: ListParams): Promise<SoftwareCatalogItem[]> {
  return getList<SoftwareCatalogItem>('/it/software', params);
}

export async function createSoftwareCatalog(
  payload: SoftwareCatalogCreate,
): Promise<SoftwareCatalogItem> {
  const { data } = await apiClient.post<SoftwareCatalogItem>('/it/software', payload);
  return data;
}

export async function updateSoftwareCatalog(
  id: string,
  payload: SoftwareCatalogUpdate,
): Promise<SoftwareCatalogItem> {
  const { data } = await apiClient.patch<SoftwareCatalogItem>(`/it/software/${id}`, payload);
  return data;
}

export async function fetchSoftwareLicenses(params?: ListParams): Promise<SoftwareLicensePool[]> {
  return getList<SoftwareLicensePool>('/it/software/licenses', params);
}

export async function createSoftwareLicense(
  payload: SoftwareLicensePoolCreate,
): Promise<SoftwareLicensePool> {
  const { data } = await apiClient.post<SoftwareLicensePool>('/it/software/licenses', payload);
  return data;
}

export async function updateSoftwareLicense(
  id: string,
  payload: SoftwareLicensePoolUpdate,
): Promise<SoftwareLicensePool> {
  const { data } = await apiClient.patch<SoftwareLicensePool>(
    `/it/software/licenses/${id}`,
    payload,
  );
  return data;
}

export async function terminateSoftwareLicense(
  id: string,
  payload: {
    termination_date?: string | null;
    reason?: string | null;
    notes?: string | null;
  },
): Promise<SoftwareLicensePool> {
  const { data } = await apiClient.post<SoftwareLicensePool>(
    `/it/software/licenses/${id}/terminate`,
    payload,
  );
  return data;
}

export async function renewSoftwareLicense(
  id: string,
  payload: {
    renewal_date?: string | null;
    period_end?: string | null;
    amount?: number | null;
    expense_id?: string | null;
    notes?: string | null;
  },
): Promise<SoftwareLicensePool> {
  const { data } = await apiClient.post<SoftwareLicensePool>(
    `/it/software/licenses/${id}/renew`,
    payload,
  );
  return data;
}

export async function fetchSoftwareAssignments(params?: ListParams): Promise<SoftwareAssignment[]> {
  return getList<SoftwareAssignment>('/it/software/assignments', params);
}

export async function createSoftwareAssignment(
  payload: SoftwareAssignmentCreate,
): Promise<SoftwareAssignment> {
  const { data } = await apiClient.post<SoftwareAssignment>('/it/software/assignments', payload);
  return data;
}

export async function unassignSoftwareAssignment(
  id: string,
  payload?: { released_date?: string | null },
): Promise<SoftwareAssignment> {
  const { data } = await apiClient.post<SoftwareAssignment>(
    `/it/software/assignments/${id}/unassign`,
    payload ?? {},
  );
  return data;
}

export async function fetchSoftwareInstallations(params?: ListParams): Promise<SoftwareInstallation[]> {
  return getList<SoftwareInstallation>('/it/software/installations', params);
}

export async function createSoftwareInstallation(payload: {
  computer_id: string;
  software_id: string;
  installed_date?: string | null;
  notes?: string | null;
}): Promise<SoftwareInstallation> {
  const { data } = await apiClient.post<SoftwareInstallation>('/it/software/installations', payload);
  return data;
}

export async function uninstallSoftwareInstallation(
  id: string,
  payload?: { uninstalled_date?: string | null },
): Promise<SoftwareInstallation> {
  const { data } = await apiClient.post<SoftwareInstallation>(
    `/it/software/installations/${id}/uninstall`,
    payload ?? {},
  );
  return data;
}

export async function fetchSoftwareRequirements(
  params?: ListParams,
): Promise<EmployeeSoftwareRequirement[]> {
  return getList<EmployeeSoftwareRequirement>('/it/software/requirements', params);
}

export async function createSoftwareRequirement(
  payload: EmployeeSoftwareRequirementCreate,
): Promise<EmployeeSoftwareRequirement> {
  const { data } = await apiClient.post<EmployeeSoftwareRequirement>(
    '/it/software/requirements',
    payload,
  );
  return data;
}

export async function updateSoftwareRequirement(
  id: string,
  payload: EmployeeSoftwareRequirementUpdate,
): Promise<EmployeeSoftwareRequirement> {
  const { data } = await apiClient.patch<EmployeeSoftwareRequirement>(
    `/it/software/requirements/${id}`,
    payload,
  );
  return data;
}

export async function deleteSoftwareRequirement(id: string): Promise<void> {
  await apiClient.delete(`/it/software/requirements/${id}`);
}

export async function fetchSoftwareExpirySummary(
  withinDays = 30,
): Promise<SoftwareExpirySummary> {
  const { data } = await apiClient.get<SoftwareExpirySummary>(
    `/it/software/expiry-summary${buildQuery({ within_days: withinDays })}`,
  );
  return data;
}

export async function fetchSoftwareCompliance(userId: string): Promise<SoftwareCompliance> {
  const { data } = await apiClient.get<SoftwareCompliance>(`/it/software/compliance/${userId}`);
  return data;
}
