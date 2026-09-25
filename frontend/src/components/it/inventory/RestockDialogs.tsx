import { useState, type FormEvent, type ReactNode } from 'react';
import { Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createRestockRequest,
  itInventoryKeys,
  releaseStockReservation,
  updateRestockRequest,
} from '../../../api/itInventory';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import type { RestockRow, StockItemRow, StockReservationRow } from '../../../types/itInventory';
import { FormField } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';

function useInventoryMutation<T>(fn: (body: T) => Promise<unknown>, message: string, onDone: () => void) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      showSuccess(message);
      onDone();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });
}

function Shell({
  title,
  subtitle,
  onClose,
  onSubmit,
  pending,
  disabled,
  submitLabel,
  children,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  onSubmit: () => void;
  pending: boolean;
  disabled: boolean;
  submitLabel: string;
  children: ReactNode;
}) {
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!disabled) onSubmit();
  }
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <form onSubmit={submit}>
        <DialogTitle>
          {title}
          {subtitle ? (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          ) : null}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {children}
          </Stack>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={onClose} disabled={pending}>
            Cancel
          </ProsohmButton>
          <ProsohmButton type="submit" buttonVariant="primary" loading={pending} disabled={disabled || pending}>
            {submitLabel}
          </ProsohmButton>
        </DialogActions>
      </form>
    </Dialog>
  );
}

export function CreateRestockDialog({ item, onClose }: { item: StockItemRow; onClose: () => void }) {
  const [qty, setQty] = useState(String(item.recommended_order_qty || item.reorder_qty || ''));
  const [expected, setExpected] = useState('');
  const [notes, setNotes] = useState('');
  const mutation = useInventoryMutation(createRestockRequest, 'Purchase request created.', onClose);
  return (
    <Shell
      title="Request restock"
      subtitle={`${item.name} · available ${item.available}${item.min_stock !== null ? ` · min ${item.min_stock}` : ''}`}
      onClose={onClose}
      pending={mutation.isPending}
      disabled={!qty || Number(qty) <= 0}
      submitLabel="Create request"
      onSubmit={() =>
        mutation.mutate({
          item_id: item.id,
          quantity: Number(qty),
          supplier_id: item.supplier_id ?? null,
          expected_date: expected || null,
          notes: notes.trim() || null,
        })
      }
    >
      <FormField
        label="Quantity"
        type="number"
        required
        value={qty}
        onChange={(e) => setQty(e.target.value)}
        slotProps={{ htmlInput: { min: 1 } }}
        helper={
          item.recommended_order_qty
            ? `Recommended: ${item.recommended_order_qty}`
            : 'No reorder needed yet; enter the quantity to order.'
        }
      />
      <FormField
        label="Expected date"
        type="date"
        value={expected}
        onChange={(e) => setExpected(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
      />
      <FormField label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
    </Shell>
  );
}

export function OrderRestockDialog({ request, onClose }: { request: RestockRow; onClose: () => void }) {
  const [po, setPo] = useState(request.purchase_order ?? '');
  const [expected, setExpected] = useState(request.expected_date ?? '');
  const mutation = useInventoryMutation(
    (body: { purchase_order: string; expected_date: string | null }) =>
      updateRestockRequest(request.id, { status: 'ordered', ...body }),
    `${request.code} marked as ordered.`,
    onClose,
  );
  return (
    <Shell
      title={`Mark ${request.code} ordered`}
      subtitle={`${request.item_name} · ${request.quantity} units`}
      onClose={onClose}
      pending={mutation.isPending}
      disabled={!po.trim()}
      submitLabel="Mark ordered"
      onSubmit={() => mutation.mutate({ purchase_order: po.trim(), expected_date: expected || null })}
    >
      <FormField label="Purchase order #" required value={po} onChange={(e) => setPo(e.target.value)} />
      <FormField
        label="Expected date"
        type="date"
        value={expected}
        onChange={(e) => setExpected(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
      />
    </Shell>
  );
}

export function CancelRestockDialog({ request, onClose }: { request: RestockRow; onClose: () => void }) {
  const [notes, setNotes] = useState('');
  const mutation = useInventoryMutation(
    (body: { notes: string | null }) => updateRestockRequest(request.id, { status: 'cancelled', ...body }),
    `${request.code} cancelled.`,
    onClose,
  );
  return (
    <Shell
      title={`Cancel ${request.code}`}
      subtitle={`${request.item_name} · ${request.outstanding_qty} outstanding`}
      onClose={onClose}
      pending={mutation.isPending}
      disabled={false}
      submitLabel="Cancel request"
      onSubmit={() => mutation.mutate({ notes: notes.trim() || null })}
    >
      <FormField label="Reason" value={notes} onChange={(e) => setNotes(e.target.value)} />
    </Shell>
  );
}

export function ReleaseReservationDialog({
  reservation,
  onClose,
}: {
  reservation: StockReservationRow;
  onClose: () => void;
}) {
  const [reason, setReason] = useState('');
  const mutation = useInventoryMutation(
    (value: string) => releaseStockReservation(reservation.id, value),
    'Reservation released.',
    onClose,
  );
  return (
    <Shell
      title="Release reservation"
      subtitle={`${reservation.quantity} × ${reservation.item_name}${reservation.for_user_name ? ` for ${reservation.for_user_name}` : ''}`}
      onClose={onClose}
      pending={mutation.isPending}
      disabled={!reason.trim()}
      submitLabel="Release"
      onSubmit={() => mutation.mutate(reason.trim())}
    >
      <FormField label="Reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
    </Shell>
  );
}
