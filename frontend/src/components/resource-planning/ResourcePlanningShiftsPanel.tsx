import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  FormControlLabel,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createShift,
  createShiftAssignment,
  endShiftAssignment,
  fetchShiftAssignments,
  fetchShiftCalendar,
  fetchShifts,
  resourceShiftKeys,
  updateShift,
} from '../../api/resourceShifts';
import { getErrorMessage } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { DashboardPanel, FormField, FormSelect } from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { QUERY_STALE_TIMES } from '../../config/queryConfig';
import {
  accessContextFromUser,
  canAssignResourceShifts,
  canManageResourceShifts,
} from '../../utils/permissions';
import type { ShiftPayload } from '../../types/ResourceShifts';

type DesignerOption = { user_id: string; designer_name: string };

type Props = {
  designers: DesignerOption[];
  teamId?: string;
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(base: string, days: number): string {
  const d = new Date(`${base}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const EMPTY_SHIFT: ShiftPayload = {
  code: '',
  name: '',
  start_time: '09:00',
  end_time: '18:00',
  break_minutes: 60,
  is_overnight: false,
  is_active: true,
  notes: '',
};

export function ResourcePlanningShiftsPanel({ designers, teamId }: Props) {
  const { user } = useAuth();
  const ctx = accessContextFromUser(user);
  const canManage = canManageResourceShifts(ctx);
  const canAssign = canAssignResourceShifts(ctx);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [subTab, setSubTab] = useState<'masters' | 'assign' | 'calendar'>('calendar');
  const [shiftForm, setShiftForm] = useState<ShiftPayload>(EMPTY_SHIFT);
  const [assignUserId, setAssignUserId] = useState('');
  const [assignShiftId, setAssignShiftId] = useState('');
  const [assignFrom, setAssignFrom] = useState(todayIso());
  const [assignType, setAssignType] = useState<'permanent' | 'rotational'>('permanent');
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    const day = (d.getDay() + 6) % 7; // Monday=0
    d.setDate(d.getDate() - day);
    return d.toISOString().slice(0, 10);
  });

  const shiftsQuery = useQuery({
    queryKey: resourceShiftKeys.shifts({ active_only: false }),
    queryFn: () => fetchShifts({ active_only: false }),
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const assignmentsQuery = useQuery({
    queryKey: resourceShiftKeys.assignments({ include_inactive: false }),
    queryFn: () => fetchShiftAssignments({ include_inactive: false }),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const calendarQuery = useQuery({
    queryKey: resourceShiftKeys.calendar({
      from: weekStart,
      to: addDaysIso(weekStart, 6),
      team_id: teamId,
    }),
    queryFn: () =>
      fetchShiftCalendar({
        from: weekStart,
        to: addDaysIso(weekStart, 6),
        team_id: teamId,
      }),
    staleTime: QUERY_STALE_TIMES.dashboard,
    enabled: subTab === 'calendar',
  });

  const createShiftMutation = useMutation({
    mutationFn: createShift,
    onSuccess: () => {
      showSuccess('Shift created');
      setShiftForm(EMPTY_SHIFT);
      void queryClient.invalidateQueries({ queryKey: resourceShiftKeys.all });
    },
    onError: (error: Error) => showError(getErrorMessage(error)),
  });

  const toggleShiftMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateShift(id, { is_active }),
    onSuccess: () => {
      showSuccess('Shift updated');
      void queryClient.invalidateQueries({ queryKey: resourceShiftKeys.all });
    },
    onError: (error: Error) => showError(getErrorMessage(error)),
  });

  const assignMutation = useMutation({
    mutationFn: createShiftAssignment,
    onSuccess: () => {
      showSuccess('Shift assigned');
      void queryClient.invalidateQueries({ queryKey: resourceShiftKeys.all });
    },
    onError: (error: Error) => showError(getErrorMessage(error)),
  });

  const endMutation = useMutation({
    mutationFn: ({ id, to }: { id: string; to: string }) => endShiftAssignment(id, to),
    onSuccess: () => {
      showSuccess('Assignment ended');
      void queryClient.invalidateQueries({ queryKey: resourceShiftKeys.all });
    },
    onError: (error: Error) => showError(getErrorMessage(error)),
  });

  const activeShifts = useMemo(
    () => (shiftsQuery.data ?? []).filter((s) => s.is_active),
    [shiftsQuery.data],
  );

  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDaysIso(weekStart, i)),
    [weekStart],
  );

  if (shiftsQuery.isLoading) return <LoadingState message="Loading shifts…" />;
  if (shiftsQuery.error) return <ErrorState error={shiftsQuery.error} />;

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
        {(
          [
            ['calendar', 'Week calendar'],
            ['assign', 'Assignments'],
            ['masters', 'Shift masters'],
          ] as const
        ).map(([key, label]) => (
          <Chip
            key={key}
            label={label}
            color={subTab === key ? 'primary' : 'default'}
            onClick={() => setSubTab(key)}
            variant={subTab === key ? 'filled' : 'outlined'}
          />
        ))}
      </Stack>

      {subTab === 'masters' && (
        <DashboardPanel title="Shift masters" subtitle="Day / evening / night definitions used by planning">
          <Stack spacing={2}>
            {(shiftsQuery.data ?? []).map((shift) => (
              <Stack
                key={shift.id}
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1}
                sx={{
                  alignItems: { sm: 'center' },
                  justifyContent: 'space-between',
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  pb: 1,
                }}
              >
                <Box>
                  <Typography variant="subtitle2">
                    {shift.code} — {shift.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {shift.start_time}–{shift.end_time}
                    {shift.is_overnight ? ' (overnight)' : ''} · break {shift.break_minutes}m
                    {!shift.is_active ? ' · inactive' : ''}
                  </Typography>
                </Box>
                {canManage && (
                  <ProsohmButton
                    size="small"
                    buttonVariant="secondary"
                    onClick={() =>
                      toggleShiftMutation.mutate({ id: shift.id, is_active: !shift.is_active })
                    }
                  >
                    {shift.is_active ? 'Deactivate' : 'Activate'}
                  </ProsohmButton>
                )}
              </Stack>
            ))}

            {canManage ? (
              <Box
                component="form"
                onSubmit={(event) => {
                  event.preventDefault();
                  createShiftMutation.mutate(shiftForm);
                }}
              >
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Add shift
                </Typography>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ flexWrap: 'wrap' }}>
                  <FormField
                    label="Code"
                    size="small"
                    value={shiftForm.code}
                    onChange={(e) => setShiftForm((p) => ({ ...p, code: e.target.value }))}
                    sx={{ width: 120 }}
                  />
                  <FormField
                    label="Name"
                    size="small"
                    value={shiftForm.name}
                    onChange={(e) => setShiftForm((p) => ({ ...p, name: e.target.value }))}
                    sx={{ width: 180 }}
                  />
                  <FormField
                    label="Start"
                    size="small"
                    value={shiftForm.start_time}
                    onChange={(e) => setShiftForm((p) => ({ ...p, start_time: e.target.value }))}
                    sx={{ width: 110 }}
                    placeholder="09:00"
                  />
                  <FormField
                    label="End"
                    size="small"
                    value={shiftForm.end_time}
                    onChange={(e) => setShiftForm((p) => ({ ...p, end_time: e.target.value }))}
                    sx={{ width: 110 }}
                    placeholder="18:00"
                  />
                  <FormField
                    label="Break (min)"
                    size="small"
                    type="number"
                    value={String(shiftForm.break_minutes)}
                    onChange={(e) =>
                      setShiftForm((p) => ({
                        ...p,
                        break_minutes: Number(e.target.value) || 0,
                      }))
                    }
                    sx={{ width: 110 }}
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={shiftForm.is_overnight}
                        onChange={(e) =>
                          setShiftForm((p) => ({ ...p, is_overnight: e.target.checked }))
                        }
                      />
                    }
                    label="Overnight"
                  />
                  <ProsohmButton type="submit" size="small" loading={createShiftMutation.isPending}>
                    Save shift
                  </ProsohmButton>
                </Stack>
              </Box>
            ) : (
              <Alert severity="info">Shift master edits require manage_resource_shifts.</Alert>
            )}
          </Stack>
        </DashboardPanel>
      )}

      {subTab === 'assign' && (
        <DashboardPanel title="Shift assignments" subtitle="Permanent or rotational coverage">
          <Stack spacing={2}>
            {canAssign ? (
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ flexWrap: 'wrap' }}>
                <FormSelect
                  label="Person"
                  size="small"
                  value={assignUserId}
                  options={[
                    { value: '', label: 'Select person' },
                    ...designers.map((d) => ({ value: d.user_id, label: d.designer_name })),
                  ]}
                  onChange={(e) => setAssignUserId(String(e.target.value))}
                  sx={{ minWidth: 200 }}
                />
                <FormSelect
                  label="Shift"
                  size="small"
                  value={assignShiftId}
                  options={[
                    { value: '', label: 'Select shift' },
                    ...activeShifts.map((s) => ({
                      value: s.id,
                      label: `${s.code} — ${s.name}`,
                    })),
                  ]}
                  onChange={(e) => setAssignShiftId(String(e.target.value))}
                  sx={{ minWidth: 200 }}
                />
                <FormSelect
                  label="Type"
                  size="small"
                  value={assignType}
                  options={[
                    { value: 'permanent', label: 'Permanent' },
                    { value: 'rotational', label: 'Rotational (weekly)' },
                  ]}
                  onChange={(e) =>
                    setAssignType(e.target.value as 'permanent' | 'rotational')
                  }
                  sx={{ minWidth: 160 }}
                />
                <TextField
                  label="Effective from"
                  type="date"
                  size="small"
                  value={assignFrom}
                  onChange={(e) => setAssignFrom(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <ProsohmButton
                  size="small"
                  loading={assignMutation.isPending}
                  onClick={() => {
                    if (!assignUserId || !assignShiftId) {
                      showError('Select a person and shift');
                      return;
                    }
                    assignMutation.mutate({
                      user_id: assignUserId,
                      shift_id: assignShiftId,
                      assignment_type: assignType,
                      rotation_pattern: assignType === 'rotational' ? 'weekly' : null,
                      rotation_weekdays:
                        assignType === 'rotational' ? [0, 1, 2, 3, 4] : [],
                      effective_from: assignFrom,
                      end_date_existing: true,
                    });
                  }}
                >
                  Assign
                </ProsohmButton>
              </Stack>
            ) : (
              <Alert severity="info">Assigning shifts requires assign_resource_shifts.</Alert>
            )}

            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Person</TableCell>
                  <TableCell>Shift</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>From</TableCell>
                  <TableCell>To</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(assignmentsQuery.data ?? []).map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.user_name ?? row.user_id}</TableCell>
                    <TableCell>
                      {row.shift_code} {row.shift_name}
                    </TableCell>
                    <TableCell>{row.assignment_type}</TableCell>
                    <TableCell>{row.effective_from}</TableCell>
                    <TableCell>{row.effective_to ?? '—'}</TableCell>
                    <TableCell align="right">
                      {canAssign && row.is_active && !row.effective_to ? (
                        <ProsohmButton
                          size="small"
                          buttonVariant="secondary"
                          onClick={() =>
                            endMutation.mutate({ id: row.id, to: todayIso() })
                          }
                        >
                          End today
                        </ProsohmButton>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
                {(assignmentsQuery.data ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Typography variant="body2" color="text.secondary">
                        No active shift assignments yet.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Stack>
        </DashboardPanel>
      )}

      {subTab === 'calendar' && (
        <DashboardPanel
          title="Shift calendar"
          subtitle="Who is on which shift this week"
          action={
            <Stack direction="row" spacing={1}>
              <ProsohmButton
                size="small"
                buttonVariant="secondary"
                onClick={() => setWeekStart(addDaysIso(weekStart, -7))}
              >
                Prev
              </ProsohmButton>
              <ProsohmButton
                size="small"
                buttonVariant="secondary"
                onClick={() => setWeekStart(addDaysIso(weekStart, 7))}
              >
                Next
              </ProsohmButton>
            </Stack>
          }
        >
          {calendarQuery.isLoading ? (
            <LoadingState message="Loading calendar…" />
          ) : calendarQuery.error ? (
            <ErrorState error={calendarQuery.error} />
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Person</TableCell>
                    {weekDays.map((day) => (
                      <TableCell key={day}>{day.slice(5)}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(calendarQuery.data?.rows ?? []).map((row) => (
                    <TableRow key={row.user_id}>
                      <TableCell>
                        <Typography variant="body2">{row.user_name}</Typography>
                        {row.team_name ? (
                          <Typography variant="caption" color="text.secondary">
                            {row.team_name}
                          </Typography>
                        ) : null}
                      </TableCell>
                      {weekDays.map((day) => {
                        const cell = row.days.find((d) => d.day === day);
                        return (
                          <TableCell key={day}>
                            {cell?.shift_code ? (
                              <Chip
                                size="small"
                                label={cell.shift_code}
                                title={cell.shift_name ?? undefined}
                              />
                            ) : (
                              <Typography variant="caption" color="text.disabled">
                                —
                              </Typography>
                            )}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                  {(calendarQuery.data?.rows ?? []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8}>
                        <Typography variant="body2" color="text.secondary">
                          No people in scope for this week. Assign shifts to see coverage.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
          )}
        </DashboardPanel>
      )}
    </Stack>
  );
}
