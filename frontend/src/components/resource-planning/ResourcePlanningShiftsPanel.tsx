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
  fetchShiftBoard,
  fetchShiftCalendar,
  fetchShiftOverview,
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

function formatShiftClock(hhmm: string): string {
  const [hRaw, mRaw] = hhmm.split(':');
  const hour24 = Number(hRaw);
  const minute = Number(mRaw);
  if (Number.isNaN(hour24) || Number.isNaN(minute)) return hhmm;
  const period = hour24 < 12 ? 'AM' : 'PM';
  const hour12 = hour24 % 12 === 0 ? 12 : hour24 % 12;
  return `${hour12}:${String(minute).padStart(2, '0')} ${period}`;
}

function shiftDisplayLabel(shift: {
  name: string;
  start_time: string;
  end_time: string;
  display_label?: string;
  display_window?: string;
}): string {
  if (shift.display_label) return shift.display_label;
  const window =
    shift.display_window ??
    `${formatShiftClock(shift.start_time)} – ${formatShiftClock(shift.end_time)}`;
  return `${shift.name} — ${window}`;
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

  const [subTab, setSubTab] = useState<'overview' | 'board' | 'masters' | 'assign' | 'calendar'>(
    'overview',
  );
  const [shiftForm, setShiftForm] = useState<ShiftPayload>(EMPTY_SHIFT);
  const [assignUserId, setAssignUserId] = useState('');
  const [assignShiftId, setAssignShiftId] = useState('');
  const [assignFrom, setAssignFrom] = useState(todayIso());
  const [assignType, setAssignType] = useState<'permanent' | 'rotational'>('permanent');
  const [rotationPattern, setRotationPattern] = useState<'weekly' | 'custom' | 'biweekly'>(
    'weekly',
  );
  const [slotDays, setSlotDays] = useState('7');
  const [rotationSeq, setRotationSeq] = useState<string[]>([]);
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    const day = (d.getDay() + 6) % 7; // Monday=0
    d.setDate(d.getDate() - day);
    return d.toISOString().slice(0, 10);
  });
  const boardDate = todayIso();

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

  const overviewQuery = useQuery({
    queryKey: resourceShiftKeys.overview({ date: boardDate, team_id: teamId }),
    queryFn: () => fetchShiftOverview({ date: boardDate, team_id: teamId }),
    staleTime: QUERY_STALE_TIMES.dashboard,
    enabled: subTab === 'overview' || subTab === 'board',
  });

  const boardQuery = useQuery({
    queryKey: resourceShiftKeys.board({ date: boardDate, team_id: teamId }),
    queryFn: () => fetchShiftBoard({ date: boardDate, team_id: teamId }),
    staleTime: QUERY_STALE_TIMES.dashboard,
    enabled: subTab === 'board',
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
      setAssignUserId('');
      setAssignShiftId('');
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
            ['overview', 'Overview'],
            ['board', 'Shift board'],
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

      {subTab === 'overview' && (
        <DashboardPanel title="Shift overview" subtitle={`Coverage for ${boardDate}`}>
          {overviewQuery.isLoading ? (
            <LoadingState message="Loading overview…" />
          ) : overviewQuery.error ? (
            <ErrorState error={overviewQuery.error} />
          ) : (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Chip label={`Employees ${overviewQuery.data?.total_employees ?? 0}`} />
                <Chip color="success" label={`Assigned ${overviewQuery.data?.assigned ?? 0}`} />
                <Chip color="warning" label={`Unassigned ${overviewQuery.data?.unassigned ?? 0}`} />
                <Chip label={`Permanent ${overviewQuery.data?.permanent ?? 0}`} />
                <Chip label={`Rotational ${overviewQuery.data?.rotational ?? 0}`} />
              </Stack>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap>
                {(overviewQuery.data?.by_shift ?? []).map((row) => (
                  <Box
                    key={row.shift_id}
                    sx={{
                      flex: 1,
                      p: 1.5,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 2,
                      minWidth: 160,
                    }}
                  >
                    <Typography variant="subtitle2">{row.display_label || row.shift_name}</Typography>
                    <Typography variant="h5" sx={{ fontWeight: 700 }}>
                      {row.employee_count}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      employees today
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </Stack>
          )}
        </DashboardPanel>
      )}

      {subTab === 'board' && (
        <DashboardPanel title="Shift board" subtitle={`Who works when · ${boardDate}`}>
          {boardQuery.isLoading ? (
            <LoadingState message="Loading board…" />
          ) : boardQuery.error ? (
            <ErrorState error={boardQuery.error} />
          ) : (
            <Stack spacing={2}>
              <Stack direction={{ xs: 'column', lg: 'row' }} spacing={1.5} sx={{ alignItems: 'stretch' }}>
                {(boardQuery.data?.columns ?? []).map((col) => (
                  <Box
                    key={col.shift_id}
                    sx={{
                      flex: 1,
                      minWidth: 220,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 2,
                      p: 1.5,
                      bgcolor: 'background.paper',
                    }}
                  >
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                      {col.display_label || col.shift_name}
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mb: 1 }}
                    >
                      {col.employee_count} employees
                    </Typography>
                    <Stack spacing={0.75}>
                      {col.employees.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No one scheduled
                        </Typography>
                      ) : (
                        col.employees.map((person) => (
                          <Box
                            key={person.user_id}
                            sx={{
                              p: 1,
                              borderRadius: 1,
                              bgcolor: 'action.hover',
                            }}
                          >
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {person.user_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {[person.team_name, person.computer_name].filter(Boolean).join(' · ') ||
                                '—'}
                            </Typography>
                            {person.next_change_date ? (
                              <Typography
                                variant="caption"
                                color="info.main"
                                sx={{ display: 'block' }}
                              >
                                Next {person.next_shift_code || 'change'} · {person.next_change_date}
                              </Typography>
                            ) : null}
                          </Box>
                        ))
                      )}
                    </Stack>
                  </Box>
                ))}
              </Stack>
              {(boardQuery.data?.unassigned ?? []).length > 0 ? (
                <Alert severity="warning">
                  Unassigned today: {(boardQuery.data?.unassigned ?? [])
                    .map((p) => p.user_name)
                    .join(', ')}
                </Alert>
              ) : null}
            </Stack>
          )}
        </DashboardPanel>
      )}

      {subTab === 'masters' && (
        <DashboardPanel title="Shift masters" subtitle="Company standard shifts used by Resource Planning">
          <Stack spacing={2}>
            {(shiftsQuery.data ?? [])
              .slice()
              .sort((a, b) => Number(b.is_active) - Number(a.is_active) || a.start_time.localeCompare(b.start_time))
              .map((shift) => (
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
                  opacity: shift.is_active ? 1 : 0.65,
                }}
              >
                <Box>
                  <Typography variant="subtitle2">{shift.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {shift.display_window ??
                      `${formatShiftClock(shift.start_time)} – ${formatShiftClock(shift.end_time)}`}
                    {shift.is_overnight ? ' (overnight)' : ''}
                    {shift.break_minutes ? ` · break ${shift.break_minutes}m` : ''}
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
                      label: shiftDisplayLabel(s),
                    })),
                  ]}
                  onChange={(e) => setAssignShiftId(String(e.target.value))}
                  sx={{ minWidth: 260 }}
                />
                <FormSelect
                  label="Type"
                  size="small"
                  value={assignType}
                  options={[
                    { value: 'permanent', label: 'Permanent' },
                    { value: 'rotational', label: 'Rotational' },
                  ]}
                  onChange={(e) =>
                    setAssignType(e.target.value as 'permanent' | 'rotational')
                  }
                  sx={{ minWidth: 160 }}
                />
                {assignType === 'rotational' ? (
                  <>
                    <FormSelect
                      label="Rotation"
                      size="small"
                      value={rotationPattern}
                      options={[
                        { value: 'weekly', label: 'Weekly (same shift)' },
                        { value: 'biweekly', label: 'Biweekly' },
                        { value: 'custom', label: 'Sequence cycle' },
                      ]}
                      onChange={(e) =>
                        setRotationPattern(
                          e.target.value as 'weekly' | 'custom' | 'biweekly',
                        )
                      }
                      sx={{ minWidth: 180 }}
                    />
                    {rotationPattern === 'custom' ? (
                      <>
                        <TextField
                          label="Days per step"
                          type="number"
                          size="small"
                          value={slotDays}
                          onChange={(e) => setSlotDays(e.target.value)}
                          sx={{ width: 120 }}
                        />
                        <FormSelect
                          label="Sequence (multi-select order)"
                          size="small"
                          value={rotationSeq[0] || ''}
                          options={[
                            { value: '', label: 'Add first shift…' },
                            ...activeShifts.map((s) => ({
                              value: s.id,
                              label: shiftDisplayLabel(s),
                            })),
                          ]}
                          onChange={(e) => {
                            const id = String(e.target.value);
                            if (!id) return;
                            setRotationSeq((prev) =>
                              prev.includes(id) ? prev : [...prev, id],
                            );
                            if (!assignShiftId) setAssignShiftId(id);
                          }}
                          sx={{ minWidth: 260 }}
                        />
                        {rotationSeq.length > 0 ? (
                          <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
                            {rotationSeq.map((id, idx) => {
                              const s = activeShifts.find((x) => x.id === id);
                              return (
                                <Chip
                                  key={`${id}-${idx}`}
                                  size="small"
                                  label={`${idx + 1}. ${s?.code || id}`}
                                  onDelete={() =>
                                    setRotationSeq((prev) => prev.filter((x) => x !== id))
                                  }
                                />
                              );
                            })}
                          </Stack>
                        ) : null}
                      </>
                    ) : null}
                  </>
                ) : null}
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
                    if (assignType === 'rotational' && rotationPattern === 'custom') {
                      if (rotationSeq.length < 2) {
                        showError('Sequence rotation needs at least two shifts');
                        return;
                      }
                    }
                    assignMutation.mutate({
                      user_id: assignUserId,
                      shift_id: assignShiftId,
                      assignment_type: assignType,
                      rotation_pattern:
                        assignType === 'rotational' ? rotationPattern : null,
                      rotation_weekdays:
                        assignType === 'rotational' && rotationPattern !== 'custom'
                          ? [0, 1, 2, 3, 4]
                          : [],
                      rotation_sequence:
                        assignType === 'rotational' && rotationPattern === 'custom'
                          ? rotationSeq
                          : [],
                      slot_days:
                        assignType === 'rotational' && rotationPattern === 'custom'
                          ? Math.max(1, Number(slotDays) || 7)
                          : null,
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
                      {row.shift_display ??
                        (row.shift_name
                          ? row.shift_name
                          : `${row.shift_code ?? ''}`.trim() || '—')}
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
                        const master = (calendarQuery.data?.shifts ?? []).find(
                          (s) => s.id === cell?.shift_id,
                        );
                        const label = master
                          ? master.name
                          : cell?.shift_name || cell?.shift_code || null;
                        const title = master
                          ? shiftDisplayLabel(master)
                          : cell?.shift_name ?? undefined;
                        return (
                          <TableCell key={day}>
                            {label ? (
                              <Chip size="small" label={label} title={title} />
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
