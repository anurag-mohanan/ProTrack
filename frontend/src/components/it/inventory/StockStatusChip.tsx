import { Chip } from '@mui/material';
import type { StockStatus } from '../../../types/itInventory';
import { STOCK_STATUS_META } from './inventoryFormat';

export function StockStatusChip({ status }: { status: StockStatus | null | undefined }) {
  if (!status) return null;
  const meta = STOCK_STATUS_META[status] ?? { label: status, color: 'default' as const };
  return <Chip size="small" label={meta.label} color={meta.color} variant={status === 'ok' ? 'outlined' : 'filled'} />;
}
