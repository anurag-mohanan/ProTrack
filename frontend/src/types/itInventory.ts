export type StockStatus = 'ok' | 'low_stock' | 'out_of_stock' | 'overstock' | 'no_minimum';

export interface StockItemRow {
  id: string;
  name: string;
  description?: string | null;
  item_kind: string;
  item_kind_label: string;
  group: string;
  sku?: string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  supplier_sku?: string | null;
  location_id?: string | null;
  location_name?: string | null;
  unit_cost?: string | number | null;
  last_purchase_date?: string | null;
  last_purchase_cost?: string | number | null;
  lead_time_days?: number | null;
  reorder_qty?: number | null;
  is_returnable: boolean;
  is_archived: boolean;
  notes?: string | null;
  pending_restock_requests: number;
  last_movement_on?: string | null;
  has_movements: boolean;
  active_alert?: { id: string; alert_type: string; since: string } | null;
  on_hand: number;
  reserved: number;
  available: number;
  incoming: number;
  min_stock: number | null;
  reorder_point: number | null;
  target_stock: number | null;
  stock_status: StockStatus;
  shortfall: number;
  recommended_order_qty: number;
  reorder_needed: boolean;
}

export interface StockMovementRow {
  id: string;
  item_id: string;
  item_name: string;
  movement_type: string;
  quantity: number;
  previous_qty: number;
  new_qty: number;
  occurred_on: string;
  recorded_at: string;
  performed_by_name?: string | null;
  employee_user_id?: string | null;
  employee_name?: string | null;
  reason?: string | null;
  reference?: string | null;
  purchase_order?: string | null;
  invoice_number?: string | null;
  unit_cost?: string | number | null;
  counterpart_location?: string | null;
  returned_qty?: number | null;
  returnable: boolean;
  ticket_id?: string | null;
}

export interface StockReservationRow {
  id: string;
  item_id: string;
  item_name: string;
  quantity: number;
  status: string;
  for_user_id?: string | null;
  for_user_name?: string | null;
  ticket_id?: string | null;
  provisioning_request_id?: string | null;
  reason?: string | null;
  reserved_by_name?: string | null;
  created_at: string;
  closed_at?: string | null;
  close_reason?: string | null;
}

export interface RestockRow {
  id: string;
  code: string;
  item_id: string;
  item_name: string;
  quantity: number;
  received_qty: number;
  outstanding_qty: number;
  status: 'requested' | 'ordered' | 'partially_received' | 'received' | 'cancelled';
  supplier_id?: string | null;
  supplier_name?: string | null;
  purchase_order?: string | null;
  expected_date?: string | null;
  requested_by_name?: string | null;
  created_at: string;
  notes?: string | null;
}

export interface StockItemDetail extends StockItemRow {
  recent_movements: StockMovementRow[];
  reservations: StockReservationRow[];
  restock_requests: RestockRow[];
}

export interface CodeLabel {
  code: string;
  label: string;
}

export interface InventoryReference {
  shifts: { id: string; code: string; label: string }[];
  roles: CodeLabel[];
  stock_kinds: CodeLabel[];
  groups: CodeLabel[];
  seat_types: CodeLabel[];
  locations: { id: string; name: string; notes?: string | null }[];
}

export interface DemandRow {
  key: string;
  label: string;
  required: number;
  committed: number;
  available: number;
  incoming: number;
  projected: number;
  shortage: boolean;
}

export interface AvailabilityByKindRow {
  key: string;
  label: string;
  assets_available: number;
  stock_available: number;
  available: number;
  stock_status: StockStatus | null;
  min_stock: number | null;
}

export interface SeatSummary {
  total_seats: number;
  complete: number;
  incomplete: number;
  no_primary_device: number;
  shared_devices: number;
  conflicts: number;
}

export interface InventoryOverview {
  physical: {
    total: number;
    in_stock: number;
    assigned: number;
    maintenance: number;
    reserved: number;
    pending_return: number;
    retired: number;
  };
  computers: {
    workstations_in_stock: number;
    laptops_in_stock: number;
    assigned: number;
    maintenance: number;
    reserved: number;
  };
  monitors: { total: number; in_stock: number; assigned: number; maintenance: number };
  by_group: ({ group: string; label: string } & Record<string, number | string>)[];
  consumables: {
    total_items: number;
    low_stock: number;
    out_of_stock: number;
    reorder_needed: number;
    incoming_units: number;
    pending_restock: number;
    no_minimum: number;
  };
  available_by_kind: AvailabilityByKindRow[];
  low_stock_items: {
    id: string;
    name: string;
    available: number;
    min_stock: number | null;
    stock_status: StockStatus;
    shortfall: number;
    recommended_order_qty: number;
    incoming: number;
  }[];
  upcoming_demand: DemandRow[];
  upcoming_shortages: number;
  virtual_seats: SeatSummary;
}

export interface SeatPerson {
  user_id: string;
  user_name?: string | null;
  shift_display?: string | null;
  reason?: string;
}

export interface SeatComponent {
  asset_id: string;
  asset_number: string;
  role: string;
  role_label: string;
  asset_type: string;
  make?: string | null;
  model?: string | null;
  status: string;
  assignment_id: string;
  assigned_date: string;
  shift_display?: string | null;
}

export interface SeatConsumable {
  item_id: string;
  name: string;
  kind: string;
  quantity: number;
  last_issued_on?: string | null;
  returnable: boolean;
}

export interface SeatRequirementState {
  role: string;
  label: string;
  required: number;
  recommended: number;
  have: number;
  state: 'ok' | 'missing_required' | 'missing_optional';
}

export interface VirtualSeatRow {
  user_id: string;
  user_name?: string | null;
  employee_code?: string | null;
  user_active: boolean;
  seat_id: string | null;
  seat_code: string | null;
  shift_id: string | null;
  shift_display: string | null;
  primary: {
    asset_id: string;
    asset_number: string;
    computer_name?: string | null;
    asset_type: string;
    make?: string | null;
    model?: string | null;
    status: string;
    is_laptop: boolean;
    assignment_id: string;
    assignment_type?: string | null;
    assigned_date: string;
  } | null;
  seat_type: string | null;
  seat_type_label: string | null;
  shared_with: SeatPerson[];
  conflicts: SeatPerson[];
  components: SeatComponent[];
  consumables: SeatConsumable[];
  counts: Record<string, number>;
  requirements: SeatRequirementState[];
  setup_status: 'complete' | 'incomplete' | 'no_primary_device';
  missing_required: string[];
  missing_optional: string[];
  is_main_seat: boolean;
}

export interface SeatHistoryRow {
  id: string;
  action: string;
  at: string | null;
  actor_name?: string | null;
  old_value: unknown;
  new_value: unknown;
}

export interface SeatRequirementConfig {
  seat_type: string;
  label: string;
  lines: { role: string; label: string; required: number; recommended: number }[];
}

export interface AvailabilitySlot {
  shift_id: string;
  shift_code: string;
  shift_display: string;
  status: string;
  reason?: string | null;
  assignee_name?: string | null;
}

export interface ComputerAvailability {
  on_date: string;
  shifts: { shift_id: string; shift_code: string; shift_display: string }[];
  summary: { seat_type: string; label: string; total: number; by_shift: Record<string, number> }[];
  computers: {
    asset_id: string;
    asset_number: string;
    computer_name?: string | null;
    asset_type: string;
    seat_type: string;
    seat_type_label: string;
    make?: string | null;
    model?: string | null;
    status: string;
    location?: string | null;
    is_laptop: boolean;
    occupants: SeatPerson[];
    shifts: AvailabilitySlot[];
  }[];
}

export interface RequirementCheckLine {
  key: string;
  label: string;
  required: number;
  available: number;
  reserved_for_request: number;
  stock_status: StockStatus | null;
  state: 'available' | 'low_stock' | 'shortage';
}

export interface ProvisioningStockCheck {
  request_id: string;
  status: string;
  lines: RequirementCheckLine[];
  reservations: StockReservationRow[];
}

export interface EmployeeItSetup {
  virtual_seats: VirtualSeatRow[];
  consumables: StockMovementRow[];
}

export interface InventoryReport {
  key: string;
  title: string;
  columns: { field: string; header: string }[];
  rows: ({ id: string } & Record<string, unknown>)[];
}
