import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  LinearProgress,
  Link,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import RadioButtonUncheckedRoundedIcon from '@mui/icons-material/RadioButtonUncheckedRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ContentCard } from '../components/ui/cards';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useToast } from '../context/ToastContext';
import { getErrorMessage } from '../api/client';
import {
  onboardingApi,
  type OnboardingChecklist,
  type OnboardingChecklistCreate,
  type OnboardingChecklistDetail,
  type OnboardingChecklistItem,
  type OnboardingChecklistUpdate,
  type OnboardingItemStatus,
} from '../api/onboarding';
import { usersApi } from '../api/resources';
import { fetchOrgDepartments, fetchRoles, fetchTeams } from '../api/lookups';
import type { OrgDepartment, Role } from '../types';
import type { Team } from '../types/Team';

const STATUS_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
];

const SECTION_SHORT: Record<string, string> = {
  'HUMAN RESOURCES': 'HR',
  ADMINISTRATION: 'Admin',
  'TEAM / MANAGER': 'Manager',
  IT: 'IT',
  ACCOUNTS: 'Accounts',
};

type FormPayload = OnboardingChecklistCreate;

export default function OnboardingPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('in_progress');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<OnboardingChecklist | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<OnboardingChecklist | null>(null);
  const [mineOnly, setMineOnly] = useState(false);

  const listQuery = useQuery({
    queryKey: ['onboarding', statusFilter],
    queryFn: () => onboardingApi.list({ status: statusFilter }),
  });

  const detailQuery = useQuery({
    queryKey: ['onboarding', selectedId],
    queryFn: () => onboardingApi.get(selectedId!),
    enabled: Boolean(selectedId),
  });

  const usersQuery = useQuery({
    queryKey: ['users', 'active-lite'],
    queryFn: () => usersApi.list({ limit: 500 }),
  });

  const departmentsQuery = useQuery({
    queryKey: ['lookups', 'org-departments'],
    queryFn: fetchOrgDepartments,
  });

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
  });

  const rolesQuery = useQuery({
    queryKey: ['lookups', 'roles'],
    queryFn: fetchRoles,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['onboarding'] });
  };

  const createMutation = useMutation({
    mutationFn: onboardingApi.create,
    onSuccess: (data) => {
      const ticketCount = data.triggered_tickets?.length ?? 0;
      showSuccess(
        ticketCount > 0
          ? `Onboarding started for ${data.employee_name}. ${ticketCount} department ticket${ticketCount === 1 ? '' : 's'} raised.`
          : `Onboarding started for ${data.employee_name}.`,
      );
      setCreateOpen(false);
      setSelectedId(data.id);
      invalidate();
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: OnboardingChecklistUpdate }) =>
      onboardingApi.update(id, payload),
    onSuccess: (data) => {
      showSuccess(`Onboarding updated for ${data.employee_name}.`);
      setEditTarget(null);
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ['onboarding', data.id] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => onboardingApi.delete(id),
    onSuccess: () => {
      showSuccess('Onboarding checklist deleted.');
      if (deleteTarget && selectedId === deleteTarget.id) {
        setSelectedId(null);
      }
      setDeleteTarget(null);
      invalidate();
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const itemMutation = useMutation({
    mutationFn: ({
      itemId,
      status,
    }: {
      itemId: string;
      status: OnboardingItemStatus;
    }) => onboardingApi.setItemStatus(selectedId!, itemId, { status }),
    onSuccess: () => {
      showSuccess('Item updated.');
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ['onboarding', selectedId] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const rows = useMemo(() => {
    const all = listQuery.data ?? [];
    if (!mineOnly) return all;
    return all.filter((row) => row.my_pending_items > 0);
  }, [listQuery.data, mineOnly]);

  const detail = detailQuery.data;

  return (
    <PageContainer>
      <PageHeader
        title="Onboarding"
        subtitle="Standard company checklist (PP-HRD-FO-14) — HR, Admin, Manager, IT, and Accounts. Selecting department / team / manager auto-routes owners and Help Desk tickets."
        action={
          <ProsohmButton
            buttonVariant="primary"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Start Onboarding
          </ProsohmButton>
        }
      />

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ mb: 1.5, alignItems: { sm: 'center' } }}
      >
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          sx={{ minWidth: 160 }}
        >
          {STATUS_FILTERS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={mineOnly}
              onChange={(event) => setMineOnly(event.target.checked)}
            />
          }
          label={<Typography variant="body2">My items only</Typography>}
        />
      </Stack>

      {listQuery.isLoading ? (
        <LoadingState message="Loading onboarding checklists…" />
      ) : rows.length === 0 ? (
        <ContentCard>
          <Typography color="text.secondary">
            No onboarding checklists match this filter. Start one when a new hire joins.
          </Typography>
        </ContentCard>
      ) : (
        <Stack spacing={0.75}>
          {rows.map((row) => (
            <ChecklistRow
              key={row.id}
              row={row}
              selected={selectedId === row.id}
              onOpen={() => setSelectedId(row.id)}
              onEdit={() => setEditTarget(row)}
              onDelete={() => setDeleteTarget(row)}
            />
          ))}
        </Stack>
      )}

      {selectedId ? (
        <Box sx={{ mt: 2.5 }}>
          {detailQuery.isLoading || !detail ? (
            <LoadingState message="Loading checklist…" />
          ) : (
            <ChecklistDetail
              detail={detail}
              mineOnly={mineOnly}
              busy={itemMutation.isPending}
              onStatus={(itemId, status) => itemMutation.mutate({ itemId, status })}
              onEdit={() => setEditTarget(detail)}
              onDelete={() => setDeleteTarget(detail)}
              onClose={() => setSelectedId(null)}
            />
          )}
        </Box>
      ) : null}

      <ChecklistFormDialog
        open={createOpen}
        mode="create"
        users={usersQuery.data ?? []}
        departments={departmentsQuery.data ?? []}
        teams={teamsQuery.data ?? []}
        roles={rolesQuery.data ?? []}
        loading={createMutation.isPending}
        onClose={() => setCreateOpen(false)}
        onSubmit={(payload) => createMutation.mutate(payload)}
      />

      <ChecklistFormDialog
        open={Boolean(editTarget)}
        mode="edit"
        initial={editTarget}
        users={usersQuery.data ?? []}
        departments={departmentsQuery.data ?? []}
        teams={teamsQuery.data ?? []}
        roles={rolesQuery.data ?? []}
        loading={updateMutation.isPending}
        onClose={() => setEditTarget(null)}
        onSubmit={(payload) => {
          if (!editTarget) return;
          updateMutation.mutate({ id: editTarget.id, payload });
        }}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete onboarding checklist?"
        recordName={deleteTarget?.employee_name}
        message="This permanently deletes the checklist and all item progress. Linked Help Desk tickets are not deleted."
        confirmLabel="Delete checklist"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </PageContainer>
  );
}

function ChecklistRow({
  row,
  selected,
  onOpen,
  onEdit,
  onDelete,
}: {
  row: OnboardingChecklist;
  selected: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <ContentCard noPadding>
      <Box
        onClick={onOpen}
        sx={{
          px: 1.5,
          py: 1,
          cursor: 'pointer',
          borderLeft: selected ? '3px solid' : '3px solid transparent',
          borderColor: selected ? 'primary.main' : 'transparent',
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <HowToRegRoundedIcon sx={{ fontSize: 18 }} color="primary" />
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {row.employee_name}
              </Typography>
              {row.employee_code ? (
                <Chip size="small" variant="outlined" label={row.employee_code} sx={{ height: 22 }} />
              ) : null}
              <Chip
                size="small"
                label={row.status_label}
                color={row.status === 'completed' ? 'success' : 'info'}
                sx={{ height: 22 }}
              />
              {row.my_pending_items > 0 ? (
                <Chip
                  size="small"
                  color="warning"
                  variant="outlined"
                  label={`${row.my_pending_items} for me`}
                  sx={{ height: 22 }}
                />
              ) : null}
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
              {[
                row.designation || row.role_name,
                row.department_name,
                row.team_name,
                row.joining_date ? `Joined ${row.joining_date}` : null,
                row.reporting_manager_name ? `Mgr: ${row.reporting_manager_name}` : null,
              ]
                .filter(Boolean)
                .join(' · ') || 'New hire'}
            </Typography>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 0.75, maxWidth: 320 }}>
              <LinearProgress
                variant="determinate"
                value={row.completion_percent}
                sx={{ flex: 1, height: 6, borderRadius: 1 }}
              />
              <Typography variant="caption" sx={{ fontWeight: 700, minWidth: 52 }}>
                {row.completed_items}/{row.total_items}
              </Typography>
            </Stack>
          </Box>
          {row.can_manage ? (
            <Stack
              direction="row"
              spacing={0.25}
              onClick={(event) => event.stopPropagation()}
              sx={{ flexShrink: 0 }}
            >
              <Tooltip title="Edit">
                <IconButton size="small" aria-label="Edit onboarding checklist" onClick={onEdit}>
                  <EditOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Delete">
                <IconButton
                  size="small"
                  color="error"
                  aria-label="Delete onboarding checklist"
                  onClick={onDelete}
                >
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
          ) : null}
        </Stack>
      </Box>
    </ContentCard>
  );
}

function sectionStats(items: OnboardingChecklistItem[]) {
  const actionable = items.filter((item) => item.status !== 'not_applicable');
  const done = actionable.filter((item) => item.status === 'completed').length;
  return { done, total: actionable.length };
}

function ChecklistDetail({
  detail,
  mineOnly,
  busy,
  onStatus,
  onEdit,
  onDelete,
  onClose,
}: {
  detail: OnboardingChecklistDetail;
  mineOnly: boolean;
  busy: boolean;
  onStatus: (itemId: string, status: OnboardingItemStatus) => void;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const bySection = useMemo(() => {
    const map = new Map<string, OnboardingChecklistItem[]>();
    for (const section of detail.sections) {
      const items = detail.items.filter((item) => item.section === section);
      const filtered = mineOnly ? items.filter((item) => item.is_mine) : items;
      if (filtered.length > 0) map.set(section, filtered);
    }
    return map;
  }, [detail, mineOnly]);

  return (
    <ContentCard>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1}
        sx={{ mb: 1.5, alignItems: { sm: 'flex-start' }, justifyContent: 'space-between' }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
            {detail.employee_name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {detail.template_code ?? 'PP-HRD-FO-14'} · {detail.completion_percent}% ·{' '}
            {[
              detail.department_name,
              detail.team_name,
              detail.role_name || detail.designation,
              detail.reporting_manager_name ? `Mgr: ${detail.reporting_manager_name}` : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </Typography>
          <Stack direction="row" spacing={0.75} sx={{ mt: 1, flexWrap: 'wrap', gap: 0.5 }}>
            {detail.sections.map((section) => {
              const items = detail.items.filter((item) => item.section === section);
              const { done, total } = sectionStats(items);
              return (
                <Chip
                  key={section}
                  size="small"
                  variant="outlined"
                  label={`${SECTION_SHORT[section] ?? section} ${done}/${total}`}
                  color={done === total && total > 0 ? 'success' : 'default'}
                  sx={{ height: 22 }}
                />
              );
            })}
          </Stack>
          {detail.triggered_tickets.length > 0 ? (
            <Stack direction="row" spacing={0.75} sx={{ mt: 1, flexWrap: 'wrap', gap: 0.5 }}>
              {detail.triggered_tickets.map((ticket) => (
                <Chip
                  key={ticket.ticket_id}
                  size="small"
                  color="info"
                  variant="outlined"
                  component={RouterLink}
                  clickable
                  to="/help-desk"
                  label={`${ticket.responsibility_label}: ${ticket.ticket_number}`}
                  sx={{ height: 22 }}
                />
              ))}
            </Stack>
          ) : null}
        </Box>
        <Stack direction="row" spacing={0.75} sx={{ flexShrink: 0 }}>
          {detail.can_manage ? (
            <>
              <ProsohmButton buttonVariant="secondary" startIcon={<EditOutlinedIcon />} onClick={onEdit}>
                Edit
              </ProsohmButton>
              <ProsohmButton
                buttonVariant="danger"
                startIcon={<DeleteOutlineRoundedIcon />}
                onClick={onDelete}
              >
                Delete
              </ProsohmButton>
            </>
          ) : null}
          <ProsohmButton buttonVariant="secondary" onClick={onClose}>
            Close
          </ProsohmButton>
        </Stack>
      </Stack>

      <Stack spacing={1.75}>
        {[...bySection.entries()].map(([section, items]) => (
          <Box key={section}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
              <Typography
                variant="overline"
                sx={{ color: 'text.secondary', letterSpacing: '0.06em', fontWeight: 700, lineHeight: 1 }}
              >
                {section}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {sectionStats(items).done}/{sectionStats(items).total}
              </Typography>
            </Stack>
            <Stack
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                overflow: 'hidden',
              }}
            >
              {items.map((item, index) => (
                <Box
                  key={item.id}
                  sx={{
                    px: 1.25,
                    py: 0.75,
                    display: 'flex',
                    gap: 1,
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    borderTop: index === 0 ? 'none' : '1px solid',
                    borderColor: 'divider',
                    bgcolor:
                      item.status === 'completed'
                        ? 'action.hover'
                        : item.is_mine
                          ? 'transparent'
                          : 'transparent',
                  }}
                >
                  <Tooltip title={item.status === 'completed' ? 'Completed' : 'Pending'}>
                    <Box sx={{ display: 'flex', color: item.status === 'completed' ? 'success.main' : 'text.disabled' }}>
                      {item.status === 'completed' ? (
                        <CheckCircleOutlineRoundedIcon sx={{ fontSize: 18 }} />
                      ) : (
                        <RadioButtonUncheckedRoundedIcon sx={{ fontSize: 18 }} />
                      )}
                    </Box>
                  </Tooltip>
                  <Box sx={{ flex: '1 1 200px', minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
                      {item.item_text}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.owner_name || item.responsibility_label}
                      {item.help_ticket_number ? (
                        <>
                          {' · '}
                          <Link component={RouterLink} to="/help-desk" underline="hover">
                            {item.help_ticket_number}
                          </Link>
                        </>
                      ) : null}
                      {item.completed_by_name
                        ? ` · ${item.completed_by_name}${item.completion_date ? ` · ${item.completion_date}` : ''}`
                        : ''}
                    </Typography>
                  </Box>
                  {item.can_edit ? (
                    <TextField
                      select
                      size="small"
                      value={item.status}
                      disabled={busy}
                      onChange={(event) =>
                        onStatus(item.id, event.target.value as OnboardingItemStatus)
                      }
                      sx={{ minWidth: 120, '& .MuiInputBase-root': { height: 32 } }}
                    >
                      <MenuItem value="pending">Pending</MenuItem>
                      <MenuItem value="completed">Done</MenuItem>
                      <MenuItem value="not_applicable">N/A</MenuItem>
                    </TextField>
                  ) : (
                    <Chip
                      size="small"
                      label={item.status_label}
                      color={
                        item.status === 'completed'
                          ? 'success'
                          : item.status === 'not_applicable'
                            ? 'default'
                            : 'warning'
                      }
                      variant={item.status === 'pending' ? 'outlined' : 'filled'}
                      sx={{ height: 22 }}
                    />
                  )}
                </Box>
              ))}
            </Stack>
          </Box>
        ))}
      </Stack>
    </ContentCard>
  );
}

function ChecklistFormDialog({
  open,
  mode,
  initial,
  users,
  departments,
  teams,
  roles,
  loading,
  onClose,
  onSubmit,
}: {
  open: boolean;
  mode: 'create' | 'edit';
  initial?: OnboardingChecklist | null;
  users: Array<{
    id: string;
    first_name: string;
    last_name: string;
    designation?: string | null;
  }>;
  departments: OrgDepartment[];
  teams: Team[];
  roles: Role[];
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: FormPayload) => void;
}) {
  const [employeeUserId, setEmployeeUserId] = useState('');
  const [employeeName, setEmployeeName] = useState('');
  const [employeeCode, setEmployeeCode] = useState('');
  const [joiningDate, setJoiningDate] = useState('');
  const [designation, setDesignation] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [teamId, setTeamId] = useState('');
  const [roleId, setRoleId] = useState('');
  const [managerId, setManagerId] = useState('');
  const [notes, setNotes] = useState('');
  const [status, setStatus] = useState<'in_progress' | 'completed' | 'cancelled'>('in_progress');

  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && initial) {
      setEmployeeUserId(initial.employee_user_id ?? '');
      setEmployeeName(initial.employee_name ?? '');
      setEmployeeCode(initial.employee_code ?? '');
      setJoiningDate(initial.joining_date ?? '');
      setDesignation(initial.designation ?? '');
      setDepartmentId(initial.org_department_id ?? '');
      setTeamId(initial.team_id ?? '');
      setRoleId(initial.role_id ?? '');
      setManagerId(initial.reporting_manager_id ?? '');
      setNotes(initial.notes ?? '');
      setStatus(initial.status);
    } else if (mode === 'create') {
      setEmployeeUserId('');
      setEmployeeName('');
      setEmployeeCode('');
      setJoiningDate('');
      setDesignation('');
      setDepartmentId('');
      setTeamId('');
      setRoleId('');
      setManagerId('');
      setNotes('');
      setStatus('in_progress');
    }
  }, [open, mode, initial]);

  const userOptions = useMemo(
    () =>
      users
        .map((user) => ({
          id: user.id,
          name: `${user.first_name} ${user.last_name}`.trim(),
          designation: user.designation ?? '',
        }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [users],
  );

  const departmentOptions = useMemo(
    () => [...departments].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)),
    [departments],
  );

  const teamOptions = useMemo(
    () => [...teams].sort((a, b) => a.name.localeCompare(b.name)),
    [teams],
  );

  const roleOptions = useMemo(
    () => [...roles].sort((a, b) => a.name.localeCompare(b.name)),
    [roles],
  );

  const handleEmployeePick = (id: string) => {
    setEmployeeUserId(id);
    const match = userOptions.find((user) => user.id === id);
    if (match) {
      setEmployeeName(match.name);
      if (match.designation) setDesignation(match.designation);
    }
  };

  const handleTeamPick = (id: string) => {
    setTeamId(id);
    const team = teamOptions.find((row) => row.id === id);
    if (team?.team_lead_id && !managerId) {
      setManagerId(team.team_lead_id);
    }
  };

  const handleRolePick = (id: string) => {
    setRoleId(id);
    const role = roleOptions.find((row) => row.id === id);
    if (role && !designation.trim()) {
      setDesignation(role.name);
    }
  };

  const handleSubmit = () => {
    if (!employeeName.trim()) return;
    const dept = departmentOptions.find((row) => row.id === departmentId);
    const payload: FormPayload & { status?: 'in_progress' | 'completed' | 'cancelled' } = {
      employee_name: employeeName.trim(),
      employee_user_id: employeeUserId || null,
      employee_code: employeeCode.trim() || null,
      joining_date: joiningDate || null,
      designation: designation.trim() || null,
      department_name: dept?.name ?? null,
      org_department_id: departmentId || null,
      team_id: teamId || null,
      role_id: roleId || null,
      reporting_manager_id: managerId || null,
      notes: notes.trim() || null,
    };
    if (mode === 'edit') {
      payload.status = status;
    }
    onSubmit(payload);
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" fullScreen={fullScreen}>
      <DialogTitle>
        {mode === 'edit' ? 'Edit onboarding' : 'Start onboarding'}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1.25} sx={{ mt: 1 }}>
          {mode === 'create' ? (
            <Typography variant="caption" color="text.secondary">
              Same 24-item checklist for every department. Creating this raises Help Desk tickets for
              HR, Admin, IT, and Accounts, and assigns manager items to the reporting manager.
            </Typography>
          ) : null}
          <TextField
            select
            fullWidth
            size="small"
            label="Link existing user (optional)"
            value={employeeUserId}
            onChange={(event) => handleEmployeePick(event.target.value)}
          >
            <MenuItem value="">— Not linked yet —</MenuItem>
            {userOptions.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            required
            fullWidth
            size="small"
            label="Employee name"
            value={employeeName}
            onChange={(event) => setEmployeeName(event.target.value)}
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
            <TextField
              fullWidth
              size="small"
              label="Employee ID"
              value={employeeCode}
              onChange={(event) => setEmployeeCode(event.target.value)}
              placeholder="e.g. PP045"
            />
            <TextField
              fullWidth
              size="small"
              type="date"
              label="Joining date"
              value={joiningDate}
              onChange={(event) => setJoiningDate(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
            <TextField
              select
              fullWidth
              size="small"
              label="Department"
              value={departmentId}
              onChange={(event) => setDepartmentId(event.target.value)}
            >
              <MenuItem value="">— Select department —</MenuItem>
              {departmentOptions.map((dept) => (
                <MenuItem key={dept.id} value={dept.id}>
                  {dept.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              fullWidth
              size="small"
              label="Team"
              value={teamId}
              onChange={(event) => handleTeamPick(event.target.value)}
            >
              <MenuItem value="">— Select team —</MenuItem>
              {teamOptions.map((team) => (
                <MenuItem key={team.id} value={team.id}>
                  {team.name}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
            <TextField
              select
              fullWidth
              size="small"
              label="Role"
              value={roleId}
              onChange={(event) => handleRolePick(event.target.value)}
            >
              <MenuItem value="">— Select role —</MenuItem>
              {roleOptions.map((role) => (
                <MenuItem key={role.id} value={role.id}>
                  {role.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              fullWidth
              size="small"
              label="Designation"
              value={designation}
              onChange={(event) => setDesignation(event.target.value)}
              helperText="Defaults from role when empty"
            />
          </Stack>
          <TextField
            select
            fullWidth
            size="small"
            label="Reporting manager"
            value={managerId}
            onChange={(event) => setManagerId(event.target.value)}
            helperText="Owns TEAM / MANAGER items; auto-fills from team lead"
          >
            <MenuItem value="">— Select —</MenuItem>
            {userOptions.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.name}
              </MenuItem>
            ))}
          </TextField>
          {mode === 'edit' ? (
            <TextField
              select
              fullWidth
              size="small"
              label="Checklist status"
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as 'in_progress' | 'completed' | 'cancelled')
              }
            >
              <MenuItem value="in_progress">In Progress</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="cancelled">Cancelled</MenuItem>
            </TextField>
          ) : null}
          <TextField
            fullWidth
            size="small"
            label="Notes"
            multiline
            minRows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <ProsohmButton buttonVariant="secondary" onClick={onClose} disabled={loading}>
          Cancel
        </ProsohmButton>
        <ProsohmButton
          buttonVariant="primary"
          onClick={handleSubmit}
          disabled={loading || !employeeName.trim()}
        >
          {mode === 'edit' ? 'Save changes' : 'Create & route'}
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}
