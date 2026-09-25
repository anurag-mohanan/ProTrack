import { useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  fetchComputerAvailability,
  fetchInventoryReference,
  itInventoryKeys,
} from '../../../api/itInventory';
import { formatCellValue } from '../../../utils/format';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { ContentCard } from '../../ui/cards';
import { FormField, FormSelect, SearchToolbar } from '../../ui/design-system';
import { SHIFT_SLOT_META } from './inventoryFormat';
import { SearchField } from './SearchField';

export function ComputerAvailabilityView() {
  const [onDate, setOnDate] = useState('');
  const [seatType, setSeatType] = useState('');
  const [shiftId, setShiftId] = useState('');
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [search, setSearch] = useState('');
  const filters = {
    on_date: onDate || undefined,
    seat_type: seatType || undefined,
    shift_id: shiftId || undefined,
    only_available: onlyAvailable || undefined,
    search: search || undefined,
  };
  const query = useQuery({
    queryKey: itInventoryKeys.availability(filters),
    queryFn: () => fetchComputerAvailability(filters),
  });
  const referenceQuery = useQuery({ queryKey: itInventoryKeys.reference(), queryFn: fetchInventoryReference });
  const data = query.data;

  return (
    <>
      <SearchToolbar sticky>
        <SearchField value={search} onChange={setSearch} placeholder="Search asset, computer, user…" />
        <FormSelect
          label="Computer type"
          value={seatType}
          onChange={(e) => setSeatType(String(e.target.value))}
          options={[
            { value: '', label: 'All types' },
            ...(referenceQuery.data?.seat_types ?? []).map((t) => ({ value: t.code, label: t.label })),
          ]}
          sx={{ minWidth: 190 }}
        />
        <FormSelect
          label="Shift"
          value={shiftId}
          onChange={(e) => setShiftId(String(e.target.value))}
          options={[
            { value: '', label: 'All shifts' },
            ...(referenceQuery.data?.shifts ?? []).map((s) => ({ value: s.id, label: s.label })),
          ]}
          sx={{ minWidth: 190 }}
        />
        <FormField
          label="On date"
          type="date"
          size="small"
          value={onDate}
          onChange={(e) => setOnDate(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <FormControlLabel
          control={<Switch checked={onlyAvailable} onChange={(e) => setOnlyAvailable(e.target.checked)} />}
          label="Only with a free shift"
        />
      </SearchToolbar>
      {query.isLoading ? <LoadingState message="Checking availability…" /> : null}
      {query.isError ? (
        <ErrorState error={query.error} title="Unable to load availability" onRetry={() => void query.refetch()} />
      ) : null}
      {data ? (
        <>
          <ContentCard title="Free computers by type and shift" subtitle={`On ${data.on_date}`}>
            {data.summary.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No computers match these filters.
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Type</TableCell>
                    <TableCell align="right">Computers</TableCell>
                    {data.shifts.map((s) => (
                      <TableCell key={s.shift_id} align="right">
                        Free · {s.shift_display}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.summary.map((row) => (
                    <TableRow key={row.seat_type}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell align="right">{row.total}</TableCell>
                      {data.shifts.map((s) => (
                        <TableCell key={s.shift_id} align="right" sx={{ fontWeight: 700 }}>
                          {row.by_shift[s.shift_code] ?? 0}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ContentCard>
          <Box sx={{ mt: 2 }}>
            <ContentCard noPadding>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Asset #</TableCell>
                    <TableCell>Computer</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Current users</TableCell>
                    {data.shifts.map((s) => (
                      <TableCell key={s.shift_id}>{s.shift_display}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.computers.map((c) => (
                    <TableRow key={c.asset_id}>
                      <TableCell>{c.asset_number}</TableCell>
                      <TableCell>{formatCellValue(c.computer_name)}</TableCell>
                      <TableCell>{c.seat_type_label}</TableCell>
                      <TableCell>{c.status.replace(/_/g, ' ')}</TableCell>
                      <TableCell>
                        {c.occupants.length
                          ? c.occupants
                              .map((o) => `${o.user_name ?? 'unknown'}${o.shift_display ? ` (${o.shift_display})` : ''}`)
                              .join(', ')
                          : '—'}
                      </TableCell>
                      {c.shifts.map((slot) => {
                        const meta = SHIFT_SLOT_META[slot.status] ?? { label: slot.status, color: 'default' as const };
                        return (
                          <TableCell key={slot.shift_id}>
                            <Tooltip title={slot.reason || slot.assignee_name || ''}>
                              <Chip
                                size="small"
                                label={slot.assignee_name && slot.status !== 'AVAILABLE' ? `${meta.label} · ${slot.assignee_name}` : meta.label}
                                color={meta.color}
                                variant={slot.status === 'AVAILABLE' ? 'filled' : 'outlined'}
                              />
                            </Tooltip>
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                  {data.computers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5 + data.shifts.length}>
                        <Typography variant="body2" color="text.secondary">
                          No computers match these filters.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </ContentCard>
          </Box>
        </>
      ) : null}
    </>
  );
}
