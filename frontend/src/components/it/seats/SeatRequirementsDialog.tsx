import { useMemo, useState } from 'react';
import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchInventoryReference,
  fetchSeatRequirements,
  itInventoryKeys,
  saveSeatRequirements,
} from '../../../api/itInventory';
import { getErrorMessage } from '../../../api/client';
import { useToast } from '../../../context/ToastContext';
import { FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';

type Line = { role: string; required: number; recommended: number };

export function SeatRequirementsDialog({
  open,
  onClose,
  canEdit,
}: {
  open: boolean;
  onClose: () => void;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [seatType, setSeatType] = useState('');
  const [drafts, setDrafts] = useState<Record<string, Line[]>>({});
  const [newRole, setNewRole] = useState('');

  const reqQuery = useQuery({ queryKey: itInventoryKeys.seatRequirements(), queryFn: fetchSeatRequirements, enabled: open });
  const refQuery = useQuery({ queryKey: itInventoryKeys.reference(), queryFn: fetchInventoryReference, enabled: open });
  const current = seatType || reqQuery.data?.[0]?.seat_type || '';
  const config = reqQuery.data?.find((r) => r.seat_type === current);
  const lines: Line[] = useMemo(
    () =>
      drafts[current] ??
      (config?.lines ?? []).map((l) => ({ role: l.role, required: l.required, recommended: l.recommended })),
    [drafts, current, config],
  );
  const roleLabel = (role: string) => refQuery.data?.roles.find((r) => r.code === role)?.label ?? role;
  const setLines = (next: Line[]) => setDrafts((prev) => ({ ...prev, [current]: next }));

  const mutation = useMutation({
    mutationFn: () => saveSeatRequirements(current, lines),
    onSuccess: async (data) => {
      queryClient.setQueryData(itInventoryKeys.seatRequirements(), data);
      await queryClient.invalidateQueries({ queryKey: itInventoryKeys.all });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[current];
        return next;
      });
      showSuccess('Seat requirements saved.');
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const usedRoles = new Set(lines.map((l) => l.role));
  const addable = (refQuery.data?.roles ?? []).filter(
    (r) => r.code !== 'computer' && r.code !== 'network' && !usedRoles.has(r.code),
  );
  const invalid = lines.some((l) => l.recommended < l.required);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        Seat setup requirements
        <Typography variant="body2" color="text.secondary">
          What a complete virtual seat needs, per computer type. Required items drive the Complete / Incomplete status.
        </Typography>
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <FormSelect
            label="Computer type"
            value={current}
            onChange={(e) => setSeatType(String(e.target.value))}
            options={(reqQuery.data ?? []).map((r) => ({ value: r.seat_type, label: r.label }))}
          />
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Component</TableCell>
                <TableCell width={120}>Required</TableCell>
                <TableCell width={140}>Recommended</TableCell>
                <TableCell width={48} />
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line, index) => (
                <TableRow key={line.role}>
                  <TableCell>{roleLabel(line.role)}</TableCell>
                  {(['required', 'recommended'] as const).map((field) => (
                    <TableCell key={field}>
                      <TextField
                        size="small"
                        type="number"
                        disabled={!canEdit}
                        value={line[field]}
                        error={field === 'recommended' && line.recommended < line.required}
                        slotProps={{ htmlInput: { min: 0, max: 8 } }}
                        onChange={(e) => {
                          const next = [...lines];
                          next[index] = { ...line, [field]: Math.max(0, Math.min(8, Number(e.target.value) || 0)) };
                          setLines(next);
                        }}
                      />
                    </TableCell>
                  ))}
                  <TableCell>
                    {canEdit ? (
                      <IconButton
                        size="small"
                        aria-label={`Remove ${roleLabel(line.role)}`}
                        onClick={() => setLines(lines.filter((_, i) => i !== index))}
                      >
                        <DeleteOutlineRoundedIcon fontSize="small" />
                      </IconButton>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {invalid ? (
            <Typography variant="caption" color="error">
              Recommended must be at least the required quantity.
            </Typography>
          ) : null}
          {canEdit && addable.length ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <FormSelect
                label="Add component"
                value={newRole}
                onChange={(e) => setNewRole(String(e.target.value))}
                options={addable.map((r) => ({ value: r.code, label: r.label }))}
              />
              <ProsohmButton
                buttonVariant="outlined"
                disabled={!newRole}
                onClick={() => {
                  setLines([...lines, { role: newRole, required: 0, recommended: 1 }]);
                  setNewRole('');
                }}
              >
                Add
              </ProsohmButton>
            </Stack>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="outlined" onClick={onClose}>
          Close
        </ProsohmButton>
        {canEdit ? (
          <ProsohmButton
            loading={mutation.isPending}
            disabled={!drafts[current] || invalid || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Save
          </ProsohmButton>
        ) : null}
      </DialogActions>
    </Dialog>
  );
}
