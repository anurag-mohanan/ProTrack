import { apiClient } from './client';
import type {
  ComputerAvailability,
  EmployeeItSetup,
  InventoryOverview,
  InventoryReference,
  InventoryReport,
  ProvisioningStockCheck,
  RestockRow,
  SeatHistoryRow,
  SeatRequirementConfig,
  SeatSummary,
  StockItemDetail,
  StockItemRow,
  StockMovementRow,
  StockReservationRow,
  VirtualSeatRow,
} from '../types/itInventory';

type Params = Record<string, string | number | boolean | undefined>;

export const itInventoryKeys = {
  all: ['it-inventory'] as const,
  reference: () => [...itInventoryKeys.all, 'reference'] as const,
  overview: () => [...itInventoryKeys.all, 'overview'] as const,
  items: (filters: Params) => [...itInventoryKeys.all, 'items', filters] as const,
  item: (id: string) => [...itInventoryKeys.all, 'item', id] as const,
  movements: (filters: Params) => [...itInventoryKeys.all, 'movements', filters] as const,
  reservations: (filters: Params) => [...itInventoryKeys.all, 'reservations', filters] as const,
  restock: (filters: Params) => [...itInventoryKeys.all, 'restock', filters] as const,
  seats: (filters: Params) => [...itInventoryKeys.all, 'seats', filters] as const,
  seatHistory: (id: string) => [...itInventoryKeys.all, 'seat-history', id] as const,
  seatRequirements: () => [...itInventoryKeys.all, 'seat-requirements'] as const,
  availability: (filters: Params) => [...itInventoryKeys.all, 'availability', filters] as const,
  provisioningCheck: (id: string) => [...itInventoryKeys.all, 'provisioning-check', id] as const,
  employee: (userId: string) => [...itInventoryKeys.all, 'employee', userId] as const,
  reportCatalog: () => [...itInventoryKeys.all, 'report-catalog'] as const,
  report: (key: string, filters: Params) => [...itInventoryKeys.all, 'report', key, filters] as const,
};

function clean(params: Params): Params {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== ''),
  );
}

export async function fetchInventoryReference() {
  const { data } = await apiClient.get<InventoryReference>('/it/inventory/reference');
  return data;
}

export async function createStockLocation(body: { name: string; notes?: string | null }) {
  const { data } = await apiClient.post('/it/inventory/locations', body);
  return data as { id: string; name: string };
}

export async function fetchInventoryOverview() {
  const { data } = await apiClient.get<InventoryOverview>('/it/inventory/overview');
  return data;
}

export async function fetchStockItems(filters: Params = {}) {
  const { data } = await apiClient.get<StockItemRow[]>('/it/inventory/items', {
    params: clean(filters),
  });
  return data;
}

export async function fetchStockItem(id: string) {
  const { data } = await apiClient.get<StockItemDetail>(`/it/inventory/items/${id}`);
  return data;
}

export type StockItemPayload = {
  name?: string;
  description?: string | null;
  item_kind?: string | null;
  sku?: string | null;
  supplier_id?: string | null;
  supplier_sku?: string | null;
  unit_cost?: number | null;
  min_stock?: number | null;
  reorder_point?: number | null;
  target_stock?: number | null;
  reorder_qty?: number | null;
  lead_time_days?: number | null;
  is_returnable?: boolean;
  location_id?: string | null;
  notes?: string | null;
  opening_qty?: number;
};

export async function createStockItem(body: StockItemPayload) {
  const { data } = await apiClient.post<StockItemRow>('/it/inventory/items', body);
  return data;
}

export async function updateStockItem(id: string, body: StockItemPayload) {
  const { data } = await apiClient.patch<StockItemRow>(`/it/inventory/items/${id}`, body);
  return data;
}

export type StockAction =
  | 'receive'
  | 'issue'
  | 'return'
  | 'adjust'
  | 'write-off'
  | 'transfer'
  | 'reserve';

export async function postStockAction(id: string, action: StockAction, body: Record<string, unknown>) {
  const { data } = await apiClient.post<StockItemRow>(`/it/inventory/items/${id}/${action}`, body);
  return data;
}

export async function fetchStockMovements(filters: Params = {}) {
  const { data } = await apiClient.get<{
    items: StockMovementRow[];
    total: number;
    limit: number;
    offset: number;
  }>('/it/inventory/movements', { params: clean(filters) });
  return data;
}

export async function fetchStockReservations(filters: Params = {}) {
  const { data } = await apiClient.get<StockReservationRow[]>('/it/inventory/reservations', {
    params: clean(filters),
  });
  return data;
}

export async function releaseStockReservation(id: string, reason: string) {
  const { data } = await apiClient.post(`/it/inventory/reservations/${id}/release`, { reason });
  return data;
}

export async function fetchRestockRequests(filters: Params = {}) {
  const { data } = await apiClient.get<RestockRow[]>('/it/inventory/restock-requests', {
    params: clean(filters),
  });
  return data;
}

export async function createRestockRequest(body: {
  item_id: string;
  quantity?: number | null;
  supplier_id?: string | null;
  expected_date?: string | null;
  notes?: string | null;
}) {
  const { data } = await apiClient.post<RestockRow>('/it/inventory/restock-requests', body);
  return data;
}

export async function updateRestockRequest(
  id: string,
  body: {
    status: 'ordered' | 'cancelled';
    purchase_order?: string | null;
    expected_date?: string | null;
    notes?: string | null;
  },
) {
  const { data } = await apiClient.patch<RestockRow>(`/it/inventory/restock-requests/${id}`, body);
  return data;
}

export async function fetchProvisioningStockCheck(requestId: string) {
  const { data } = await apiClient.get<ProvisioningStockCheck>(
    `/it/inventory/provisioning/${requestId}/check`,
  );
  return data;
}

export async function fetchEmployeeItSetup(userId: string) {
  const { data } = await apiClient.get<EmployeeItSetup>(`/it/inventory/employee/${userId}`);
  return data;
}

export async function fetchVirtualSeats(filters: Params = {}) {
  const { data } = await apiClient.get<{ seats: VirtualSeatRow[]; summary: SeatSummary }>(
    '/it/virtual-seats',
    { params: clean(filters) },
  );
  return data;
}

export async function fetchSeatHistory(seatId: string) {
  const { data } = await apiClient.get<SeatHistoryRow[]>(`/it/virtual-seats/${seatId}/history`);
  return data;
}

export async function fetchSeatRequirements() {
  const { data } = await apiClient.get<SeatRequirementConfig[]>('/it/virtual-seats/requirements');
  return data;
}

export async function saveSeatRequirements(
  seatType: string,
  lines: { role: string; required: number; recommended: number }[],
) {
  const { data } = await apiClient.put<SeatRequirementConfig[]>(
    `/it/virtual-seats/requirements/${seatType}`,
    { lines },
  );
  return data;
}

export async function fetchComputerAvailability(filters: Params = {}) {
  const { data } = await apiClient.get<ComputerAvailability>('/it/availability/computers', {
    params: clean(filters),
  });
  return data;
}

export async function fetchInventoryReportCatalog() {
  const { data } = await apiClient.get<{ key: string; title: string }[]>('/it/inventory/reports');
  return data;
}

export async function fetchInventoryReport(key: string, filters: Params = {}) {
  const { data } = await apiClient.get<InventoryReport>(`/it/inventory/reports/${key}`, {
    params: clean(filters),
  });
  return data;
}
