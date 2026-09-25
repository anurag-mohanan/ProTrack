import {
  Alert,
  Box,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import EventSeatRoundedIcon from '@mui/icons-material/EventSeatRounded';
import { useQuery } from '@tanstack/react-query';
import { fetchSeatHistory, itInventoryKeys } from '../../../api/itInventory';
import type { VirtualSeatRow } from '../../../types/itInventory';
import { formatCellValue, formatDate, formatDateTime } from '../../../utils/format';
import { ModernDrawer } from '../../ui/design-system';
import { SEAT_STATUS_META } from '../inventory/inventoryFormat';

const HISTORY_LABELS: Record<string, string> = {
  it_virtual_seat_created: 'Seat created',
  it_virtual_seat_primary_changed: 'Primary device changed',
  it_virtual_seat_components_changed: 'Components changed',
  it_virtual_seat_ended: 'Seat ended',
};

function describe(value: unknown): string {
  if (!value || typeof value !== 'object') return value ? String(value) : '';
  const v = value as Record<string, unknown>;
  const parts: string[] = [];
  if (Array.isArray(v.added) && v.added.length) parts.push(`Added ${v.added.join(', ')}`);
  if (Array.isArray(v.removed) && v.removed.length) parts.push(`Removed ${v.removed.join(', ')}`);
  if (v.primary_device) parts.push(`Primary ${String(v.primary_device)}`);
  if (v.shift) parts.push(String(v.shift));
  if (v.ended_on) parts.push(`Ended ${String(v.ended_on)}`);
  return parts.join(' · ');
}

export function VirtualSeatDetailDrawer({ seat, onClose }: { seat: VirtualSeatRow | null; onClose: () => void }) {
  const historyQuery = useQuery({
    queryKey: itInventoryKeys.seatHistory(seat?.seat_id ?? ''),
    queryFn: () => fetchSeatHistory(seat!.seat_id!),
    enabled: Boolean(seat?.seat_id),
  });
  const status = seat ? SEAT_STATUS_META[seat.setup_status] : null;

  return (
    <ModernDrawer
      open={Boolean(seat)}
      onClose={onClose}
      title={seat ? `${seat.user_name ?? 'Employee'}${seat.seat_code ? ` · ${seat.seat_code}` : ''}` : 'Virtual seat'}
      subtitle={seat ? [seat.shift_display, seat.seat_type_label].filter(Boolean).join(' · ') || undefined : undefined}
      icon={EventSeatRoundedIcon}
      widthPreset="detail"
      width="min(720px, 100vw)"
    >
      {seat ? (
        <Stack spacing={2.5}>
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            {status ? <Chip size="small" label={status.label} color={status.color} /> : null}
            {seat.shared_with.length ? <Chip size="small" variant="outlined" label="Shared workstation" /> : null}
            {!seat.user_active ? <Chip size="small" color="error" label="Employee inactive" /> : null}
          </Stack>
          <Alert severity="info" variant="outlined">
            A virtual seat is derived from this employee&apos;s active computer assignment and the peripherals assigned to
            them. Change it by assigning or returning assets.
          </Alert>
          {seat.conflicts.length ? (
            <Alert severity="error">
              Overlapping assignment on the same device:{' '}
              {seat.conflicts.map((c) => `${c.user_name ?? 'unknown'} (${c.shift_display ?? 'no shift'})`).join(', ')}
            </Alert>
          ) : null}

          <Typography variant="subtitle2">Primary device</Typography>
          {seat.primary ? (
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 700 }}>
                {seat.primary.asset_number}
                {seat.primary.computer_name ? ` · ${seat.primary.computer_name}` : ''}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {[seat.primary.asset_type, seat.primary.make, seat.primary.model].filter(Boolean).join(' · ')} · assigned{' '}
                {formatDate(seat.primary.assigned_date)}
              </Typography>
            </Box>
          ) : (
            <Alert severity="warning">No computer assigned. Peripherals are listed below.</Alert>
          )}
          {seat.shared_with.length ? (
            <Typography variant="body2">
              Shared with:{' '}
              {seat.shared_with.map((s) => `${s.user_name ?? 'unknown'} (${s.shift_display ?? 'no shift'})`).join(', ')}
            </Typography>
          ) : null}

          {seat.requirements.length ? (
            <>
              <Divider />
              <Typography variant="subtitle2">Setup requirements ({seat.seat_type_label})</Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Component</TableCell>
                    <TableCell align="right">Required</TableCell>
                    <TableCell align="right">Recommended</TableCell>
                    <TableCell align="right">Assigned</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {seat.requirements.map((line) => (
                    <TableRow key={line.role}>
                      <TableCell>{line.label}</TableCell>
                      <TableCell align="right">{line.required}</TableCell>
                      <TableCell align="right">{line.recommended}</TableCell>
                      <TableCell align="right">{line.have}</TableCell>
                      <TableCell>
                        {line.state === 'ok' ? (
                          <Chip size="small" color="success" variant="outlined" label="OK" />
                        ) : line.state === 'missing_required' ? (
                          <Chip size="small" color="error" label="Missing (required)" />
                        ) : (
                          <Chip size="small" color="warning" variant="outlined" label="Below recommended" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          ) : null}

          <Divider />
          <Typography variant="subtitle2">Assigned peripherals</Typography>
          {seat.components.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {seat.is_main_seat ? 'No peripherals assigned.' : 'Peripherals are shown on this employee’s main seat.'}
            </Typography>
          ) : (
            <List dense disablePadding>
              {seat.components.map((c) => (
                <ListItem key={c.assignment_id} disableGutters>
                  <ListItemText
                    primary={`${c.role_label} · ${c.asset_number}`}
                    secondary={`${[c.asset_type, c.make, c.model].filter(Boolean).join(' · ')} · since ${formatDate(c.assigned_date)}`}
                  />
                </ListItem>
              ))}
            </List>
          )}
          {seat.consumables.length ? (
            <>
              <Typography variant="subtitle2">Consumables held</Typography>
              <List dense disablePadding>
                {seat.consumables.map((c) => (
                  <ListItem key={c.item_id} disableGutters>
                    <ListItemText
                      primary={`${c.quantity} × ${c.name}`}
                      secondary={`Last issued ${formatDate(c.last_issued_on)}${c.returnable ? ' · returnable' : ''}`}
                    />
                  </ListItem>
                ))}
              </List>
            </>
          ) : null}

          {seat.seat_id ? (
            <>
              <Divider />
              <Typography variant="subtitle2">Seat history</Typography>
              {historyQuery.data && historyQuery.data.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No history recorded.
                </Typography>
              ) : null}
              <List dense disablePadding>
                {(historyQuery.data ?? []).map((h) => (
                  <ListItem key={h.id} disableGutters>
                    <ListItemText
                      primary={`${HISTORY_LABELS[h.action] ?? h.action}${describe(h.new_value) ? ` — ${describe(h.new_value)}` : ''}`}
                      secondary={`${formatDateTime(h.at)} · ${formatCellValue(h.actor_name)}`}
                    />
                  </ListItem>
                ))}
              </List>
            </>
          ) : null}
        </Stack>
      ) : null}
    </ModernDrawer>
  );
}
