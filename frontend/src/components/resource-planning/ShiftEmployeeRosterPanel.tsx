import { Fragment, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Collapse,
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
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded';
import KeyboardArrowUpRoundedIcon from '@mui/icons-material/KeyboardArrowUpRounded';
import { useQuery } from '@tanstack/react-query';
import { fetchEmployeeRoster, fetchShiftAssignments, resourceShiftKeys } from '../../api/resourceShifts';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { EmployeeShiftChip } from '../common/EmployeePicker';
import { DashboardPanel, FormSelect } from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import type { EmployeeRosterParams, EmployeeRosterRow, Shift } from '../../types/ResourceShifts';

type StatusFilter = 'active' | 'inactive' | 'all';

type Props = {
  shifts: Shift[];
  canAssign: boolean;
  onAssign: (row: EmployeeRosterRow) => void;
};

function clock(value: string | null): string {
  return value ? value.slice(0, 5) : '—';
}

function ShiftHistory({ userId }: { userId: string }) {
  const query = useQuery({
    queryKey: resourceShiftKeys.assignments({ user_id: userId, include_inactive: true }),
    queryFn: () => fetchShiftAssignments({ user_id: userId, include_inactive: true }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });
  if (query.isLoading) return <LoadingState message="Loading shift history…" />;
  if (query.error) return <ErrorState error={query.error} />;
  const rows = query.data ?? [];
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No shift has ever been assigned to this employee.
      </Typography>
    );
  }
  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Shift</TableCell>
          <TableCell>Type</TableCell>
          <TableCell>Effective from</TableCell>
          <TableCell>Effective to</TableCell>
          <TableCell>Status</TableCell>
          <TableCell>Notes</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell>{row.shift_display ?? row.shift_name ?? row.shift_code ?? '—'}</TableCell>
            <TableCell>{row.assignment_type}</TableCell>
            <TableCell>{row.effective_from}</TableCell>
            <TableCell>{row.effective_to ?? 'Open'}</TableCell>
            <TableCell>{row.is_active ? 'Active' : 'Cancelled'}</TableCell>
            <TableCell>{row.notes ?? ''}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** Every employee from the User master with their shift today — including those without one. */
export function ShiftEmployeeRosterPanel({ shifts, canAssign, onAssign }: Props) {
  const [status, setStatus] = useState<StatusFilter>('active');
  const [shift, setShift] = useState('');
  const [department, setDepartment] = useState('');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const q = useDebouncedValue(search.trim(), 250);

  const params: EmployeeRosterParams = { status, shift: shift || undefined, q: q || undefined };
  const rosterQuery = useQuery({
    queryKey: resourceShiftKeys.roster(params),
    queryFn: () => fetchEmployeeRoster(params),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const departments = useMemo(
    () =>
      Array.from(new Set((rosterQuery.data?.rows ?? []).map((r) => r.department).filter(Boolean) as string[])).sort(),
    [rosterQuery.data],
  );
  const rows = useMemo(
    () => (rosterQuery.data?.rows ?? []).filter((r) => !department || r.department === department),
    [rosterQuery.data, department],
  );
  const counts = rosterQuery.data?.counts;

  return (
    <DashboardPanel
      title="Employees"
      subtitle={`Every employee from the Employee Master with their shift on ${rosterQuery.data?.on_date ?? 'today'}`}
    >
      <Stack spacing={2}>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
          {(
            [
              ['all', 'All'],
              ['active', 'Active'],
              ['inactive', 'Inactive'],
            ] as const
          ).map(([key, label]) => (
            <Chip
              key={key}
              label={label}
              color={status === key ? 'primary' : 'default'}
              variant={status === key ? 'filled' : 'outlined'}
              onClick={() => setStatus(key)}
            />
          ))}
          <Box sx={{ width: 8 }} />
          {[{ value: '', label: 'Any shift' }, { value: 'none', label: 'No shift' }, ...shifts.map((s) => ({ value: s.code, label: s.name }))].map(
            (opt) => (
              <Chip
                key={opt.value || 'any'}
                label={opt.label}
                color={shift === opt.value ? 'primary' : 'default'}
                variant={shift === opt.value ? 'filled' : 'outlined'}
                onClick={() => setShift(opt.value)}
              />
            ),
          )}
        </Stack>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
          <TextField
            size="small"
            label="Search"
            placeholder="Name, employee ID, department, designation"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ minWidth: 300 }}
          />
          <FormSelect
            label="Department"
            size="small"
            value={department}
            options={[{ value: '', label: 'All departments' }, ...departments.map((d) => ({ value: d, label: d }))]}
            onChange={(e) => setDepartment(String(e.target.value))}
            sx={{ minWidth: 220 }}
          />
        </Stack>
        {counts ? (
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <Chip label={`Listed ${counts.total}`} />
            <Chip color="success" label={`Assigned ${counts.assigned}`} />
            <Chip color="warning" label={`Not assigned ${counts.not_assigned}`} />
            {counts.inactive ? <Chip label={`Inactive ${counts.inactive}`} /> : null}
            {Object.entries(counts.by_shift).map(([code, n]) => (
              <Chip key={code} variant="outlined" label={`${code} ${n}`} />
            ))}
          </Stack>
        ) : null}

        {rosterQuery.isLoading ? (
          <LoadingState message="Loading employees…" />
        ) : rosterQuery.error ? (
          <ErrorState error={rosterQuery.error} />
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell />
                  <TableCell>Employee</TableCell>
                  <TableCell>Employee ID</TableCell>
                  <TableCell>Department</TableCell>
                  <TableCell>Designation</TableCell>
                  <TableCell>Manager</TableCell>
                  <TableCell>Current shift</TableCell>
                  <TableCell>Start</TableCell>
                  <TableCell>End</TableCell>
                  <TableCell>Effective from</TableCell>
                  <TableCell>Effective to</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <Fragment key={row.user_id}>
                    <TableRow hover>
                      <TableCell padding="checkbox">
                        <IconButton
                          size="small"
                          aria-label="Shift history"
                          onClick={() => setExpanded(expanded === row.user_id ? null : row.user_id)}
                        >
                          {expanded === row.user_id ? (
                            <KeyboardArrowUpRoundedIcon fontSize="small" />
                          ) : (
                            <KeyboardArrowDownRoundedIcon fontSize="small" />
                          )}
                        </IconButton>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {row.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {row.email}
                        </Typography>
                      </TableCell>
                      <TableCell>{row.employee_code ?? '—'}</TableCell>
                      <TableCell>{row.department ?? '—'}</TableCell>
                      <TableCell>{row.designation ?? '—'}</TableCell>
                      <TableCell>{row.manager_name ?? '—'}</TableCell>
                      <TableCell>{row.shift_name ?? (row.is_active ? 'Not Assigned' : '—')}</TableCell>
                      <TableCell>{clock(row.shift_start)}</TableCell>
                      <TableCell>{clock(row.shift_end)}</TableCell>
                      <TableCell>{row.effective_from ?? '—'}</TableCell>
                      <TableCell>{row.effective_to ?? (row.assignment_id ? 'Open' : '—')}</TableCell>
                      <TableCell>
                        <EmployeeShiftChip row={row} />
                      </TableCell>
                      <TableCell align="right">
                        {canAssign && row.is_active ? (
                          <ProsohmButton size="small" buttonVariant="secondary" onClick={() => onAssign(row)}>
                            {row.shift_state === 'ASSIGNED' ? 'Change shift' : 'Assign shift'}
                          </ProsohmButton>
                        ) : null}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell colSpan={13} sx={{ py: 0, borderBottom: expanded === row.user_id ? undefined : 'none' }}>
                        <Collapse in={expanded === row.user_id} unmountOnExit>
                          <Box sx={{ py: 1.5 }}>
                            <ShiftHistory userId={row.user_id} />
                          </Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </Fragment>
                ))}
                {rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={13}>
                      <Typography variant="body2" color="text.secondary">
                        No employees match these filters.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </Box>
        )}
      </Stack>
    </DashboardPanel>
  );
}
