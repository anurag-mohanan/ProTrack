import { useState } from 'react';
import {
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchProvisioningStockCheck,
  fetchStockItems,
  itInventoryKeys,
  postStockAction,
} from '../../../api/itInventory';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import type { RequirementCheckLine } from '../../../types/itInventory';
import { FormField, FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';

const STATE_META: Record<RequirementCheckLine['state'], { label: string; color: 'success' | 'warning' | 'error' }> = {
  available: { label: 'Available', color: 'success' },
  low_stock: { label: 'Low stock', color: 'warning' },
  shortage: { label: 'Shortage', color: 'error' },
};

function ReserveDialog({
  requestId,
  line,
  forUserId,
  onClose,
}: {
  requestId: string;
  line: RequirementCheckLine;
  forUserId?: string | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [itemId, setItemId] = useState('');
  const [qty, setQty] = useState(String(Math.max(line.required - line.reserved_for_request, 1)));
  const itemsQuery = useQuery({
    queryKey: itInventoryKeys.items({ kind: line.key }),
    queryFn: () => fetchStockItems({ kind: line.key }),
  });
  const mutation = useMutation({
    mutationFn: () =>
      postStockAction(itemId, 'reserve', {
        quantity: Number(qty),
        provisioning_request_id: requestId,
        for_user_id: forUserId || undefined,
        reason: 'Onboarding requirement',
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      showSuccess('Stock reserved for this request.');
      onClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });
  const options = (itemsQuery.data ?? [])
    .filter((i) => i.available > 0)
    .map((i) => ({ value: i.id, label: `${i.name} · ${i.available} available` }));
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>Reserve {line.label}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          {options.length === 0 && !itemsQuery.isLoading ? (
            <Typography variant="body2" color="text.secondary">
              No stock item of this kind has free units.
            </Typography>
          ) : (
            <FormSelect
              label="Stock item"
              value={itemId}
              onChange={(e) => setItemId(String(e.target.value))}
              options={options}
            />
          )}
          <FormField
            label="Quantity"
            type="number"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            slotProps={{ htmlInput: { min: 1 } }}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="outlined" onClick={onClose}>
          Cancel
        </ProsohmButton>
        <ProsohmButton
          loading={mutation.isPending}
          disabled={!itemId || Number(qty) <= 0 || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          Reserve
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

export function ProvisioningStockCheckPanel({
  requestId,
  employeeUserId,
  canReserve,
}: {
  requestId: string;
  employeeUserId?: string | null;
  canReserve: boolean;
}) {
  const [reserving, setReserving] = useState<RequirementCheckLine | null>(null);
  const query = useQuery({
    queryKey: itInventoryKeys.provisioningCheck(requestId),
    queryFn: () => fetchProvisioningStockCheck(requestId),
  });
  if (query.isLoading) {
    return (
      <Typography variant="body2" color="text.secondary">
        Checking stock…
      </Typography>
    );
  }
  if (query.isError || !query.data) return null;
  const { lines, reservations } = query.data;
  if (lines.length === 0) return null;

  return (
    <>
      <Typography variant="subtitle2">Inventory check</Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Requirement</TableCell>
            <TableCell align="right">Required</TableCell>
            <TableCell align="right">Free now</TableCell>
            <TableCell align="right">Reserved here</TableCell>
            <TableCell>State</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {lines.map((line) => {
            const meta = STATE_META[line.state];
            const consumable = !line.key.startsWith('computer') && line.key !== 'monitor';
            return (
              <TableRow key={line.key}>
                <TableCell>{line.label}</TableCell>
                <TableCell align="right">{line.required}</TableCell>
                <TableCell align="right">{line.available}</TableCell>
                <TableCell align="right">{line.reserved_for_request}</TableCell>
                <TableCell>
                  <Chip size="small" label={meta.label} color={meta.color} />
                </TableCell>
                <TableCell align="right">
                  {canReserve && consumable && line.reserved_for_request < line.required ? (
                    <Button size="small" onClick={() => setReserving(line)}>
                      Reserve
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {reservations.length ? (
        <Typography variant="caption" color="text.secondary">
          Reserved for this request: {reservations.map((r) => `${r.quantity} × ${r.item_name}`).join(', ')}. Released
          automatically if the request is cancelled.
        </Typography>
      ) : null}
      {reserving ? (
        <ReserveDialog
          requestId={requestId}
          line={reserving}
          forUserId={employeeUserId}
          onClose={() => setReserving(null)}
        />
      ) : null}
    </>
  );
}
