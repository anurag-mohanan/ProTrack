import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import Inventory2RoundedIcon from '@mui/icons-material/Inventory2Rounded';
import { useQuery } from '@tanstack/react-query';
import { fetchStockItem, itInventoryKeys, type StockAction } from '../../../api/itInventory';
import type { RestockRow, StockReservationRow } from '../../../types/itInventory';
import { formatCellValue, formatDate } from '../../../utils/format';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { ModernDrawer } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import {
  ASSIGN_ACTIONS,
  MANAGE_ACTIONS,
  MOVEMENT_TYPE_LABELS,
  RESTOCK_STATUS_META,
  STOCK_ACTION_LABELS,
} from './inventoryFormat';
import {
  CancelRestockDialog,
  CreateRestockDialog,
  OrderRestockDialog,
  ReleaseReservationDialog,
} from './RestockDialogs';
import { StockActionDialog } from './StockActionDialog';
import { StockStatusChip } from './StockStatusChip';

type Props = {
  itemId: string | null;
  onClose: () => void;
  onEdit: () => void;
  canManage: boolean;
  canAssign: boolean;
};

function Metric({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <Box sx={{ minWidth: 96 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
        {value === null || value === undefined || value === '' ? '—' : value}
      </Typography>
    </Box>
  );
}

export function StockItemDetailDrawer({ itemId, onClose, onEdit, canManage, canAssign }: Props) {
  const [action, setAction] = useState<StockAction | null>(null);
  const [restockOpen, setRestockOpen] = useState(false);
  const [ordering, setOrdering] = useState<RestockRow | null>(null);
  const [cancelling, setCancelling] = useState<RestockRow | null>(null);
  const [releasing, setReleasing] = useState<StockReservationRow | null>(null);
  const query = useQuery({
    queryKey: itInventoryKeys.item(itemId ?? ''),
    queryFn: () => fetchStockItem(itemId!),
    enabled: Boolean(itemId),
  });
  const item = query.data;
  const actions = [...(canManage ? MANAGE_ACTIONS : []), ...(canAssign || canManage ? ASSIGN_ACTIONS : [])];

  return (
    <ModernDrawer
      open={Boolean(itemId)}
      onClose={onClose}
      title={item?.name ?? 'Stock item'}
      subtitle={item ? `${item.item_kind_label}${item.location_name ? ` · ${item.location_name}` : ''}` : undefined}
      icon={Inventory2RoundedIcon}
      widthPreset="detail"
      width="min(760px, 100vw)"
    >
      {query.isLoading ? <LoadingState message="Loading stock item…" /> : null}
      {query.isError ? <ErrorState error={query.error} title="Unable to load stock item" /> : null}
      {item ? (
        <Stack spacing={2.5}>
          <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <StockStatusChip status={item.stock_status} />
            {item.reorder_needed ? <Chip size="small" color="warning" variant="outlined" label="Reorder needed" /> : null}
            {item.is_returnable ? <Chip size="small" variant="outlined" label="Returnable" /> : null}
            {item.active_alert ? (
              <Chip
                size="small"
                color="error"
                variant="outlined"
                label={`Alert since ${formatDate(String(item.active_alert.since))}`}
              />
            ) : null}
          </Stack>
          <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <Metric label="On hand" value={item.on_hand} />
            <Metric label="Reserved" value={item.reserved} />
            <Metric label="Available" value={item.available} />
            <Metric label="Incoming" value={item.incoming} />
            <Metric label="Minimum" value={item.min_stock} />
            <Metric label="Shortfall" value={item.shortfall || null} />
          </Stack>
          {item.stock_status === 'out_of_stock' || item.stock_status === 'low_stock' ? (
            <Alert severity={item.stock_status === 'out_of_stock' ? 'error' : 'warning'}>
              {item.stock_status === 'out_of_stock' ? 'OUT OF STOCK.' : 'Below minimum stock.'}{' '}
              {item.recommended_order_qty
                ? `Recommended order: ${item.recommended_order_qty}.`
                : item.incoming
                  ? `${item.incoming} already incoming.`
                  : ''}
            </Alert>
          ) : null}
          {actions.length || canManage ? (
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {actions.map((key) => (
                <ProsohmButton key={key} size="small" buttonVariant="outlined" onClick={() => setAction(key)}>
                  {STOCK_ACTION_LABELS[key]}
                </ProsohmButton>
              ))}
              {canManage ? (
                <>
                  <ProsohmButton size="small" buttonVariant="outlined" onClick={() => setRestockOpen(true)}>
                    Request restock
                  </ProsohmButton>
                  <ProsohmButton size="small" buttonVariant="outlined" onClick={onEdit}>
                    Edit item
                  </ProsohmButton>
                </>
              ) : null}
            </Stack>
          ) : null}
          <Divider />
          <Typography variant="subtitle2">Reorder information</Typography>
          <Stack direction="row" spacing={3} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <Metric label="Reorder point" value={item.reorder_point} />
            <Metric label="Target stock" value={item.target_stock} />
            <Metric label="Reorder qty" value={item.reorder_qty} />
            <Metric label="Supplier" value={item.supplier_name} />
            <Metric label="Supplier SKU" value={item.supplier_sku} />
            <Metric label="Internal SKU" value={item.sku} />
            <Metric label="Lead time" value={item.lead_time_days !== null && item.lead_time_days !== undefined ? `${item.lead_time_days} d` : null} />
            <Metric label="Last purchase" value={formatDate(item.last_purchase_date) || null} />
            <Metric label="Last cost" value={item.last_purchase_cost as string | null} />
          </Stack>

          <Divider />
          <Typography variant="subtitle2">Active reservations</Typography>
          {item.reservations.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No active reservations.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Qty</TableCell>
                  <TableCell>For</TableCell>
                  <TableCell>Reason</TableCell>
                  <TableCell>Reserved by</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {item.reservations.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.quantity}</TableCell>
                    <TableCell>{formatCellValue(r.for_user_name)}</TableCell>
                    <TableCell>{formatCellValue(r.reason)}</TableCell>
                    <TableCell>{formatCellValue(r.reserved_by_name)}</TableCell>
                    <TableCell align="right">
                      {canAssign || canManage ? (
                        <Button size="small" onClick={() => setReleasing(r)}>
                          Release
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <Divider />
          <Typography variant="subtitle2">Restock requests</Typography>
          {item.restock_requests.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No restock requests.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Code</TableCell>
                  <TableCell>Qty</TableCell>
                  <TableCell>Received</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>PO</TableCell>
                  <TableCell>Expected</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {item.restock_requests.map((r) => {
                  const meta = RESTOCK_STATUS_META[r.status];
                  const open = r.status === 'requested' || r.status === 'ordered' || r.status === 'partially_received';
                  return (
                    <TableRow key={r.id}>
                      <TableCell>{r.code}</TableCell>
                      <TableCell>{r.quantity}</TableCell>
                      <TableCell>{r.received_qty}</TableCell>
                      <TableCell>
                        <Chip size="small" label={meta?.label ?? r.status} color={meta?.color ?? 'default'} />
                      </TableCell>
                      <TableCell>{formatCellValue(r.purchase_order)}</TableCell>
                      <TableCell>{formatDate(r.expected_date) || '—'}</TableCell>
                      <TableCell align="right">
                        {canManage && r.status === 'requested' ? (
                          <Button size="small" onClick={() => setOrdering(r)}>
                            Mark ordered
                          </Button>
                        ) : null}
                        {canManage && r.status !== 'requested' && open ? (
                          <Button size="small" onClick={() => setAction('receive')}>
                            Receive
                          </Button>
                        ) : null}
                        {canManage && open ? (
                          <Button size="small" onClick={() => setCancelling(r)}>
                            Cancel
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}

          <Divider />
          <Typography variant="subtitle2">Movement history</Typography>
          {item.recent_movements.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No movements recorded.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell align="right">Qty</TableCell>
                  <TableCell align="right">Balance</TableCell>
                  <TableCell>Employee</TableCell>
                  <TableCell>By</TableCell>
                  <TableCell>Reason / ref</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {item.recent_movements.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>{formatDate(m.occurred_on)}</TableCell>
                    <TableCell>{MOVEMENT_TYPE_LABELS[m.movement_type] ?? m.movement_type}</TableCell>
                    <TableCell align="right">{m.quantity > 0 ? `+${m.quantity}` : m.quantity}</TableCell>
                    <TableCell align="right">
                      {m.previous_qty} → {m.new_qty}
                    </TableCell>
                    <TableCell>{formatCellValue(m.employee_name)}</TableCell>
                    <TableCell>{formatCellValue(m.performed_by_name)}</TableCell>
                    <TableCell>
                      {[m.reason, m.reference, m.purchase_order && `PO ${m.purchase_order}`, m.counterpart_location]
                        .filter(Boolean)
                        .join(' · ') || '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Stack>
      ) : null}
      <StockActionDialog itemId={action ? itemId : null} action={action} onClose={() => setAction(null)} />
      {restockOpen && item ? <CreateRestockDialog item={item} onClose={() => setRestockOpen(false)} /> : null}
      {ordering ? <OrderRestockDialog request={ordering} onClose={() => setOrdering(null)} /> : null}
      {cancelling ? <CancelRestockDialog request={cancelling} onClose={() => setCancelling(null)} /> : null}
      {releasing ? <ReleaseReservationDialog reservation={releasing} onClose={() => setReleasing(null)} /> : null}
    </ModernDrawer>
  );
}
