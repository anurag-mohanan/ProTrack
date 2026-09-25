import { useMemo, useState, type FormEvent } from 'react';
import {
  Alert,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchInventoryReference,
  fetchStockItem,
  itInventoryKeys,
  postStockAction,
  type StockAction,
} from '../../../api/itInventory';
import { fetchMasterSuppliers } from '../../../api/itOperations';
import { fetchUsers } from '../../../api/lookups';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import { FormField, FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { userDisplayName } from '../../../utils/format';
import { STOCK_ACTION_LABELS } from './inventoryFormat';

type Props = {
  itemId: string | null;
  action: StockAction | null;
  onClose: () => void;
};

const today = () => new Date().toISOString().slice(0, 10);

export function StockActionDialog({ itemId, action, onClose }: Props) {
  const open = Boolean(itemId && action);
  return open ? (
    <StockActionForm key={`${itemId}-${action}`} itemId={itemId!} action={action!} onClose={onClose} />
  ) : null;
}

function StockActionForm({ itemId, action, onClose }: { itemId: string; action: StockAction; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState<Record<string, string>>({
    quantity: action === 'adjust' ? '' : '1',
    received_on: today(),
    movement_type: 'damage',
  });
  const set = (key: string) => (value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const itemQuery = useQuery({ queryKey: itInventoryKeys.item(itemId), queryFn: () => fetchStockItem(itemId) });
  const needsUsers = action === 'issue' || action === 'reserve' || action === 'return';
  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
    enabled: needsUsers,
  });
  const suppliersQuery = useQuery({
    queryKey: ['it-master', 'suppliers', 'active'],
    queryFn: () => fetchMasterSuppliers({ active_only: true }),
    enabled: action === 'receive',
  });
  const referenceQuery = useQuery({
    queryKey: itInventoryKeys.reference(),
    queryFn: fetchInventoryReference,
    enabled: action === 'transfer',
  });

  const item = itemQuery.data;
  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? [])
        .filter((u) => u.is_active !== false)
        .map((u) => ({ value: u.id, label: userDisplayName(u) || u.email || u.id })),
    [usersQuery.data],
  );
  const openIssues = useMemo(
    () =>
      (item?.recent_movements ?? []).filter(
        (m) => m.movement_type === 'issue' && Math.abs(m.quantity) - (m.returned_qty ?? 0) > 0,
      ),
    [item],
  );

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => postStockAction(itemId, action, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      showSuccess(`${STOCK_ACTION_LABELS[action]} recorded.`);
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const num = (key: string) => (form[key] ? Number(form[key]) : undefined);
  const str = (key: string) => (form[key]?.trim() ? form[key].trim() : undefined);

  function buildBody(): Record<string, unknown> {
    switch (action) {
      case 'receive':
        return {
          quantity: num('quantity'),
          received_on: str('received_on'),
          supplier_id: str('supplier_id'),
          purchase_order: str('purchase_order'),
          invoice_number: str('invoice_number'),
          unit_cost: num('unit_cost'),
          restock_request_id: str('restock_request_id'),
          notes: str('notes'),
        };
      case 'issue':
        return {
          quantity: num('quantity'),
          employee_user_id: str('employee_user_id'),
          reason: str('reason'),
          reference: str('reference'),
          reservation_id: str('reservation_id'),
        };
      case 'return':
        return {
          quantity: num('quantity'),
          issue_movement_id: str('issue_movement_id'),
          employee_user_id: str('employee_user_id'),
          reason: str('reason'),
        };
      case 'adjust':
        return { counted_qty: num('quantity'), reason: str('reason') };
      case 'write-off':
        return { movement_type: form.movement_type, quantity: num('quantity'), reason: str('reason') };
      case 'transfer':
        return { quantity: num('quantity'), to_location_id: str('to_location_id'), reason: str('reason') };
      case 'reserve':
        return { quantity: num('quantity'), for_user_id: str('for_user_id'), reason: str('reason') };
    }
  }

  const reasonRequired = action === 'adjust' || action === 'write-off';
  const missing =
    form.quantity === '' ||
    (action !== 'adjust' && Number(form.quantity) <= 0) ||
    (action === 'issue' && !form.employee_user_id) ||
    (action === 'transfer' && !form.to_location_id) ||
    (reasonRequired && !form.reason?.trim());

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!missing) mutation.mutate(buildBody());
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>
          {STOCK_ACTION_LABELS[action]}
          {item ? (
            <Typography variant="body2" color="text.secondary">
              {item.name} · on hand {item.on_hand} · reserved {item.reserved} · available {item.available}
            </Typography>
          ) : null}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {action === 'return' && item && !item.is_returnable ? (
              <Alert severity="warning">This item is not returnable; the return will be rejected.</Alert>
            ) : null}
            {action === 'write-off' ? (
              <FormSelect
                label="Type"
                value={form.movement_type}
                onChange={(e) => set('movement_type')(String(e.target.value))}
                options={[
                  { value: 'damage', label: 'Damaged' },
                  { value: 'dispose', label: 'Disposed' },
                ]}
              />
            ) : null}
            <FormField
              label={action === 'adjust' ? 'Counted quantity on hand' : 'Quantity'}
              type="number"
              required
              value={form.quantity}
              onChange={(e) => set('quantity')(e.target.value)}
              slotProps={{ htmlInput: { min: action === 'adjust' ? 0 : 1 } }}
              helper={
                action === 'adjust' && item
                  ? `Current on hand: ${item.on_hand}. Cannot go below reserved (${item.reserved}).`
                  : undefined
              }
            />
            {action === 'receive' ? (
              <>
                <FormField
                  label="Received on"
                  type="date"
                  value={form.received_on}
                  onChange={(e) => set('received_on')(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <FormSelect
                  label="Restock request"
                  value={form.restock_request_id ?? ''}
                  onChange={(e) => set('restock_request_id')(String(e.target.value))}
                  options={[
                    { value: '', label: 'None' },
                    ...(item?.restock_requests ?? [])
                      .filter((r) => r.status === 'ordered' || r.status === 'partially_received')
                      .map((r) => ({
                        value: r.id,
                        label: `${r.code} · ${r.outstanding_qty} outstanding${r.purchase_order ? ` · PO ${r.purchase_order}` : ''}`,
                      })),
                  ]}
                />
                <FormSelect
                  label="Supplier"
                  searchable
                  value={form.supplier_id ?? ''}
                  onChange={(e) => set('supplier_id')(String(e.target.value))}
                  options={(suppliersQuery.data ?? []).map((s) => ({ value: s.id, label: s.name }))}
                />
                <Stack direction="row" spacing={2}>
                  <FormField
                    label="Purchase order"
                    value={form.purchase_order ?? ''}
                    onChange={(e) => set('purchase_order')(e.target.value)}
                  />
                  <FormField
                    label="Invoice #"
                    value={form.invoice_number ?? ''}
                    onChange={(e) => set('invoice_number')(e.target.value)}
                  />
                </Stack>
                <FormField
                  label="Unit cost"
                  type="number"
                  value={form.unit_cost ?? ''}
                  onChange={(e) => set('unit_cost')(e.target.value)}
                  slotProps={{ htmlInput: { min: 0, step: '0.01' } }}
                />
              </>
            ) : null}
            {action === 'issue' ? (
              <>
                <FormSelect
                  label="Employee"
                  searchable
                  required
                  value={form.employee_user_id ?? ''}
                  onChange={(e) => set('employee_user_id')(String(e.target.value))}
                  options={userOptions}
                />
                <FormSelect
                  label="Fulfil reservation"
                  value={form.reservation_id ?? ''}
                  onChange={(e) => set('reservation_id')(String(e.target.value))}
                  options={[
                    { value: '', label: 'None (free stock)' },
                    ...(item?.reservations ?? []).map((r) => ({
                      value: r.id,
                      label: `${r.quantity} for ${r.for_user_name ?? 'unassigned'}${r.reason ? ` · ${r.reason}` : ''}`,
                    })),
                  ]}
                />
                <FormField
                  label="Reference (ticket / request)"
                  value={form.reference ?? ''}
                  onChange={(e) => set('reference')(e.target.value)}
                />
              </>
            ) : null}
            {action === 'return' ? (
              <FormSelect
                label="Original issue"
                value={form.issue_movement_id ?? ''}
                onChange={(e) => set('issue_movement_id')(String(e.target.value))}
                options={[
                  { value: '', label: 'Not linked' },
                  ...openIssues.map((m) => ({
                    value: m.id,
                    label: `${m.occurred_on} · ${m.employee_name ?? 'unknown'} · ${Math.abs(m.quantity) - (m.returned_qty ?? 0)} outstanding`,
                  })),
                ]}
              />
            ) : null}
            {action === 'return' && !form.issue_movement_id ? (
              <FormSelect
                label="Returned by"
                searchable
                value={form.employee_user_id ?? ''}
                onChange={(e) => set('employee_user_id')(String(e.target.value))}
                options={userOptions}
              />
            ) : null}
            {action === 'reserve' ? (
              <FormSelect
                label="Reserved for"
                searchable
                value={form.for_user_id ?? ''}
                onChange={(e) => set('for_user_id')(String(e.target.value))}
                options={userOptions}
              />
            ) : null}
            {action === 'transfer' ? (
              <FormSelect
                label="To location"
                required
                value={form.to_location_id ?? ''}
                onChange={(e) => set('to_location_id')(String(e.target.value))}
                options={(referenceQuery.data?.locations ?? [])
                  .filter((loc) => loc.id !== item?.location_id)
                  .map((loc) => ({ value: loc.id, label: loc.name }))}
                helper="Add locations from the Inventory page if the list is empty."
              />
            ) : null}
            {action === 'receive' ? (
              <FormField
                label="Notes"
                multiline
                minRows={2}
                value={form.notes ?? ''}
                onChange={(e) => set('notes')(e.target.value)}
              />
            ) : (
              <FormField
                label="Reason"
                required={reasonRequired}
                value={form.reason ?? ''}
                onChange={(e) => set('reason')(e.target.value)}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            type="submit"
            buttonVariant="primary"
            loading={mutation.isPending}
            disabled={missing || mutation.isPending}
          >
            Save
          </ProsohmButton>
        </DialogActions>
      </form>
    </Dialog>
  );
}
