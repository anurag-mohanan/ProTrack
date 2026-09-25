import type { StockAction } from '../../../api/itInventory';
import type { StockStatus } from '../../../types/itInventory';

export const STOCK_ACTION_LABELS: Record<StockAction, string> = {
  receive: 'Receive stock',
  issue: 'Issue to employee',
  return: 'Return to stock',
  adjust: 'Adjust (stock count)',
  'write-off': 'Damage / dispose',
  transfer: 'Transfer location',
  reserve: 'Reserve',
};

export const MANAGE_ACTIONS: StockAction[] = ['receive', 'adjust', 'write-off', 'transfer'];
export const ASSIGN_ACTIONS: StockAction[] = ['issue', 'return', 'reserve'];

type ChipColor = 'default' | 'success' | 'warning' | 'error' | 'info';

export const STOCK_STATUS_META: Record<StockStatus, { label: string; color: ChipColor }> = {
  ok: { label: 'OK', color: 'success' },
  low_stock: { label: 'Low stock', color: 'warning' },
  out_of_stock: { label: 'Out of stock', color: 'error' },
  overstock: { label: 'Overstock', color: 'info' },
  no_minimum: { label: 'No minimum set', color: 'default' },
};

export const STOCK_STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'low_stock', label: 'Low stock' },
  { value: 'out_of_stock', label: 'Out of stock' },
  { value: 'reorder', label: 'Reorder needed' },
  { value: 'incoming', label: 'Incoming' },
  { value: 'ok', label: 'OK' },
  { value: 'overstock', label: 'Overstock' },
  { value: 'no_minimum', label: 'No minimum set' },
];

export const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  opening_balance: 'Opening balance',
  receive: 'Received',
  issue: 'Issued',
  return: 'Returned',
  adjust: 'Adjustment',
  damage: 'Damaged',
  dispose: 'Disposed',
  transfer_out: 'Transfer out',
  transfer_in: 'Transfer in',
};

export const RESTOCK_STATUS_META: Record<string, { label: string; color: ChipColor }> = {
  requested: { label: 'Requested', color: 'info' },
  ordered: { label: 'Ordered', color: 'warning' },
  partially_received: { label: 'Partially received', color: 'warning' },
  received: { label: 'Received', color: 'success' },
  cancelled: { label: 'Cancelled', color: 'default' },
};

export const SEAT_STATUS_META: Record<string, { label: string; color: ChipColor }> = {
  complete: { label: 'Complete', color: 'success' },
  incomplete: { label: 'Incomplete', color: 'warning' },
  no_primary_device: { label: 'No primary device', color: 'error' },
};

export const SHIFT_SLOT_META: Record<string, { label: string; color: ChipColor }> = {
  AVAILABLE: { label: 'Available', color: 'success' },
  ASSIGNED: { label: 'Assigned', color: 'info' },
  CONFLICT: { label: 'Conflict', color: 'error' },
  UNAVAILABLE: { label: 'Unavailable', color: 'default' },
};

export function toCsv(columns: { field: string; header: string }[], rows: Record<string, unknown>[]): string {
  const esc = (value: unknown) => {
    const text = value === null || value === undefined ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [
    columns.map((c) => esc(c.header)).join(','),
    ...rows.map((row) => columns.map((c) => esc(row[c.field])).join(',')),
  ].join('\n');
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
