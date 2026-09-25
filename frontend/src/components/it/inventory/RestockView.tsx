import { useState } from 'react';
import {
  Button,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchRestockRequests, fetchStockReservations, itInventoryKeys } from '../../../api/itInventory';
import type { RestockRow, StockReservationRow } from '../../../types/itInventory';
import { formatCellValue, formatDate, formatDateTime } from '../../../utils/format';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { ContentCard } from '../../ui/cards';
import { FormSelect, SearchToolbar } from '../../ui/design-system';
import { RESTOCK_STATUS_META } from './inventoryFormat';
import { CancelRestockDialog, OrderRestockDialog, ReleaseReservationDialog } from './RestockDialogs';
import { StockActionDialog } from './StockActionDialog';

const OPEN = new Set(['requested', 'ordered', 'partially_received']);

export function RestockView({ canManage, canAssign }: { canManage: boolean; canAssign: boolean }) {
  const [status, setStatus] = useState('open');
  const [ordering, setOrdering] = useState<RestockRow | null>(null);
  const [cancelling, setCancelling] = useState<RestockRow | null>(null);
  const [receivingItem, setReceivingItem] = useState<string | null>(null);
  const [releasing, setReleasing] = useState<StockReservationRow | null>(null);

  const restockQuery = useQuery({
    queryKey: itInventoryKeys.restock({ status }),
    queryFn: () => fetchRestockRequests({ status: status || undefined }),
  });
  const reservationsQuery = useQuery({
    queryKey: itInventoryKeys.reservations({ status: 'active' }),
    queryFn: () => fetchStockReservations({ status: 'active' }),
  });

  return (
    <Stack spacing={2.5}>
      <ContentCard
        title="Restock requests"
        subtitle="Purchase request → order → receive. Receiving updates stock and closes the request."
      >
        <SearchToolbar>
          <FormSelect
            label="Status"
            value={status}
            onChange={(e) => setStatus(String(e.target.value))}
            options={[
              { value: 'open', label: 'Open' },
              { value: '', label: 'All' },
              ...Object.entries(RESTOCK_STATUS_META).map(([value, meta]) => ({ value, label: meta.label })),
            ]}
            sx={{ minWidth: 170 }}
          />
        </SearchToolbar>
        {restockQuery.isLoading ? <LoadingState message="Loading restock requests…" /> : null}
        {restockQuery.isError ? <ErrorState error={restockQuery.error} title="Unable to load restock requests" /> : null}
        {restockQuery.data && restockQuery.data.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No restock requests. Create one from a low-stock item.
          </Typography>
        ) : null}
        {restockQuery.data && restockQuery.data.length > 0 ? (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Code</TableCell>
                <TableCell>Item</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell align="right">Received</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Supplier</TableCell>
                <TableCell>PO</TableCell>
                <TableCell>Expected</TableCell>
                <TableCell>Requested by</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {restockQuery.data.map((r) => {
                const meta = RESTOCK_STATUS_META[r.status];
                return (
                  <TableRow key={r.id}>
                    <TableCell>{r.code}</TableCell>
                    <TableCell>{r.item_name}</TableCell>
                    <TableCell align="right">{r.quantity}</TableCell>
                    <TableCell align="right">{r.received_qty}</TableCell>
                    <TableCell>
                      <Chip size="small" label={meta?.label ?? r.status} color={meta?.color ?? 'default'} />
                    </TableCell>
                    <TableCell>{formatCellValue(r.supplier_name)}</TableCell>
                    <TableCell>{formatCellValue(r.purchase_order)}</TableCell>
                    <TableCell>{formatDate(r.expected_date) || '—'}</TableCell>
                    <TableCell>{formatCellValue(r.requested_by_name)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                      {canManage && r.status === 'requested' ? (
                        <Button size="small" onClick={() => setOrdering(r)}>
                          Mark ordered
                        </Button>
                      ) : null}
                      {canManage && (r.status === 'ordered' || r.status === 'partially_received') ? (
                        <Button size="small" onClick={() => setReceivingItem(r.item_id)}>
                          Receive
                        </Button>
                      ) : null}
                      {canManage && OPEN.has(r.status) ? (
                        <Button size="small" color="inherit" onClick={() => setCancelling(r)}>
                          Cancel
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : null}
      </ContentCard>

      <ContentCard title="Active reservations" subtitle="Reserved units are excluded from available stock.">
        {reservationsQuery.isLoading ? <LoadingState message="Loading reservations…" /> : null}
        {reservationsQuery.isError ? (
          <ErrorState error={reservationsQuery.error} title="Unable to load reservations" />
        ) : null}
        {reservationsQuery.data && reservationsQuery.data.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No active reservations.
          </Typography>
        ) : null}
        {reservationsQuery.data && reservationsQuery.data.length > 0 ? (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Item</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell>For</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Reserved</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {reservationsQuery.data.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.item_name}</TableCell>
                  <TableCell align="right">{r.quantity}</TableCell>
                  <TableCell>{formatCellValue(r.for_user_name)}</TableCell>
                  <TableCell>
                    {r.provisioning_request_id ? 'Onboarding request' : r.ticket_id ? 'Ticket' : 'Manual'}
                  </TableCell>
                  <TableCell>{formatCellValue(r.reason)}</TableCell>
                  <TableCell>
                    {formatDateTime(r.created_at)} · {formatCellValue(r.reserved_by_name)}
                  </TableCell>
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
        ) : null}
      </ContentCard>
      {ordering ? <OrderRestockDialog request={ordering} onClose={() => setOrdering(null)} /> : null}
      {cancelling ? <CancelRestockDialog request={cancelling} onClose={() => setCancelling(null)} /> : null}
      {releasing ? <ReleaseReservationDialog reservation={releasing} onClose={() => setReleasing(null)} /> : null}
      <StockActionDialog
        itemId={receivingItem}
        action={receivingItem ? 'receive' : null}
        onClose={() => setReceivingItem(null)}
      />
    </Stack>
  );
}
