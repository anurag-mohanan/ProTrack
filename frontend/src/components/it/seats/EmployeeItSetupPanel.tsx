import { useMemo } from 'react';
import { Box, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchEmployeeItSetup, itInventoryKeys } from '../../../api/itInventory';
import { formatDate } from '../../../utils/format';
import { SEAT_STATUS_META } from '../inventory/inventoryFormat';

/** IT SETUP: the employee's derived virtual seat(s) and consumables still held. */
export function EmployeeItSetupPanel({ userId }: { userId: string }) {
  const query = useQuery({
    queryKey: itInventoryKeys.employee(userId),
    queryFn: () => fetchEmployeeItSetup(userId),
    retry: false,
  });
  const held = useMemo(() => {
    const map = new Map<string, { name: string; quantity: number; last: string; returnable: boolean }>();
    for (const m of query.data?.consumables ?? []) {
      if (m.movement_type !== 'issue') continue;
      const outstanding = Math.abs(m.quantity) - (m.returned_qty ?? 0);
      if (outstanding <= 0) continue;
      const row = map.get(m.item_id) ?? { name: m.item_name, quantity: 0, last: m.occurred_on, returnable: m.returnable };
      row.quantity += outstanding;
      if (m.occurred_on > row.last) row.last = m.occurred_on;
      map.set(m.item_id, row);
    }
    return [...map.entries()];
  }, [query.data]);

  if (query.isLoading || query.isError || !query.data) return null;
  const seats = query.data.virtual_seats;
  if (seats.length === 0 && held.length === 0) return null;

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        IT setup
      </Typography>
      <Stack spacing={1.5}>
        {seats.map((seat) => {
          const meta = SEAT_STATUS_META[seat.setup_status];
          const other = Object.entries(seat.counts)
            .filter(([role, n]) => n && role !== 'monitor' && role !== 'mouse_3d')
            .map(([role, n]) => {
              const label =
                seat.components.find((c) => c.role === role)?.role_label ??
                seat.consumables.find((c) => c.kind === role)?.name ??
                role;
              return n > 1 ? `${label} ×${n}` : label;
            });
          return (
            <Table size="small" key={seat.seat_id ?? `${seat.user_id}-${seat.primary?.asset_id ?? 'none'}`}>
              <TableBody>
                <TableRow>
                  <TableCell width="30%">Virtual seat</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                      <span>{seat.seat_code ?? '—'}</span>
                      {meta ? <Chip size="small" label={meta.label} color={meta.color} /> : null}
                      {seat.missing_required.length ? (
                        <Typography variant="caption" color="error.main">
                          Missing: {seat.missing_required.join(', ')}
                        </Typography>
                      ) : null}
                    </Stack>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Shift</TableCell>
                  <TableCell>{seat.shift_display ?? '—'}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Primary device</TableCell>
                  <TableCell>
                    {seat.primary
                      ? `${seat.primary.asset_number}${seat.primary.computer_name ? ` · ${seat.primary.computer_name}` : ''} (${seat.seat_type_label})`
                      : 'No computer assigned'}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Monitors / 3D mouse</TableCell>
                  <TableCell>
                    {seat.counts.monitor ?? 0} / {seat.counts.mouse_3d ? 'Yes' : 'No'}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Other</TableCell>
                  <TableCell>{other.join(', ') || '—'}</TableCell>
                </TableRow>
                {seat.shared_with.length ? (
                  <TableRow>
                    <TableCell>Shared with</TableCell>
                    <TableCell>
                      {seat.shared_with
                        .map((s) => `${s.user_name ?? 'unknown'} (${s.shift_display ?? 'no shift'})`)
                        .join(', ')}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          );
        })}
        {held.length ? (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Consumables held</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell>Last issued</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {held.map(([id, row]) => (
                <TableRow key={id}>
                  <TableCell>
                    {row.name}
                    {row.returnable ? '' : ' (non-returnable)'}
                  </TableCell>
                  <TableCell align="right">{row.quantity}</TableCell>
                  <TableCell>{formatDate(row.last)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : null}
      </Stack>
    </Box>
  );
}
