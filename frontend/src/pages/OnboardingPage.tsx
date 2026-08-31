import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  InputAdornment,
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
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import PublishRoundedIcon from '@mui/icons-material/PublishRounded';
import RadioButtonUncheckedRoundedIcon from '@mui/icons-material/RadioButtonUncheckedRounded';
import UnfoldLessRoundedIcon from '@mui/icons-material/UnfoldLessRounded';
import UnfoldMoreRoundedIcon from '@mui/icons-material/UnfoldMoreRounded';
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
  const [publishTarget, setPublishTarget] = useState<OnboardingChecklist | null>(null);
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
      const passwordNote = data.provisioned_temporary_password
        ? ` Login password: ${data.provisioned_temporary_password} (share with the new hire).`
        : '';
      showSuccess(
        ticketCount > 0
          ? `Onboarding started for ${data.employee_name}. ${ticketCount} department ticket${ticketCount === 1 ? '' : 's'} raised.${passwordNote}`
          : `Onboarding started for ${data.employee_name}.${passwordNote}`,
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

  const publishMutation = useMutation({
    mutationFn: (id: string) => onboardingApi.publish(id),
    onSuccess: (data) => {
      showSuccess(`Onboarding checklist published for ${data.employee_name}.`);
      setPublishTarget(null);
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ['onboarding', data.id] });
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
              onPublish={() => setPublishTarget(row)}
              onDelete={() => setDeleteTarget(row)}
            />
          ))}
        </Stack>
      )}

      {selectedId ? (
        <Box sx={{ mt: 1.5 }}>
          {detailQuery.isLoading || !detail ? (
            <LoadingState message="Loading checklist…" />
          ) : (
            <ChecklistDetail
              detail={detail}
              mineOnly={mineOnly}
              busy={itemMutation.isPending}
              onStatus={(itemId, status) => itemMutation.mutate({ itemId, status })}
              onEdit={() => setEditTarget(detail)}
              onPublish={() => setPublishTarget(detail)}
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

      <ConfirmDialog
        open={Boolean(publishTarget)}
        title="Publish onboarding checklist?"
        recordName={publishTarget?.employee_name}
        message="Publishing locks this checklist as the official record. After publish, it cannot be deleted."
        confirmLabel="Publish"
        loading={publishMutation.isPending}
        onClose={() => setPublishTarget(null)}
        onConfirm={() => {
          if (publishTarget) publishMutation.mutate(publishTarget.id);
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
  onPublish,
  onDelete,
}: {
  row: OnboardingChecklist;
  selected: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onPublish: () => void;
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
              {row.is_published ? (
                <Chip size="small" color="success" variant="outlined" label="Published" sx={{ height: 22 }} />
              ) : null}
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
              {!row.is_published ? (
                <Tooltip title="Publish">
                  <IconButton
                    size="small"
                    color="primary"
                    aria-label="Publish onboarding checklist"
                    onClick={onPublish}
                  >
                    <PublishRoundedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : null}
              {!row.is_published ? (
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
              ) : null}
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
  onPublish,
  onDelete,
  onClose,
}: {
  detail: OnboardingChecklistDetail;
  mineOnly: boolean;
  busy: boolean;
  onStatus: (itemId: string, status: OnboardingItemStatus) => void;
  onEdit: () => void;
  onPublish: () => void;
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

  const sectionKeys = useMemo(() => [...bySection.keys()], [bySection]);

  const [minimized, setMinimized] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => new Set(sectionKeys));

  useEffect(() => {
    const open = new Set<string>();
    for (const [section, items] of bySection.entries()) {
      const { done, total } = sectionStats(items);
      if (done < total) open.add(section);
    }
    if (open.size === 0 && sectionKeys[0]) open.add(sectionKeys[0]);
    setExpandedSections(open);
    setMinimized(false);
    // Reset only when switching to another checklist.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  const toggleSection = (section: string) => {
    setExpandedSections((current) => {
      const next = new Set(current);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  const expandAll = () => setExpandedSections(new Set(sectionKeys));
  const collapseAll = () => setExpandedSections(new Set());

  if (minimized) {
    return (
      <ContentCard noPadding>
        <Stack
          direction="row"
          spacing={1}
          sx={{
            px: 1.25,
            py: 0.85,
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
            flexWrap: 'wrap',
          }}
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', minWidth: 0, flex: 1 }}>
            <HowToRegRoundedIcon sx={{ fontSize: 18 }} color="primary" />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                {detail.employee_name}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {detail.template_code ?? 'PP-HRD-FO-14'} · {detail.completion_percent}% ·{' '}
                {detail.completed_items}/{detail.total_items} done
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={detail.completion_percent}
              sx={{ width: { xs: 72, sm: 120 }, height: 6, borderRadius: 1, flexShrink: 0 }}
            />
          </Stack>
          <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
            <Tooltip title="Expand checklist">
              <IconButton
                size="small"
                aria-label="Expand onboarding checklist"
                onClick={() => setMinimized(false)}
              >
                <UnfoldMoreRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Close">
              <IconButton size="small" aria-label="Close onboarding checklist" onClick={onClose}>
                <CloseRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        </Stack>
      </ContentCard>
    );
  }

  return (
    <ContentCard noPadding>
      <Box sx={{ p: { xs: 1.25, sm: 1.5 } }}>
      <Stack
        direction="row"
        spacing={1}
        sx={{ mb: 1, alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 800, lineHeight: 1.25 }}>
            {detail.employee_name}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
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
          <Stack direction="row" spacing={0.5} sx={{ mt: 0.75, flexWrap: 'wrap', gap: 0.5 }}>
            {detail.is_published ? (
              <Chip
                size="small"
                color="success"
                variant="outlined"
                label="Published"
                sx={{ height: 20, '& .MuiChip-label': { px: 0.75, fontSize: '0.7rem' } }}
              />
            ) : null}
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
                  sx={{ height: 20, '& .MuiChip-label': { px: 0.75, fontSize: '0.7rem' } }}
                />
              );
            })}
          </Stack>
          {detail.triggered_tickets.length > 0 ? (
            <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
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
                  sx={{ height: 20, '& .MuiChip-label': { px: 0.75, fontSize: '0.7rem' } }}
                />
              ))}
            </Stack>
          ) : null}
        </Box>
        <Stack direction="row" spacing={0.15} sx={{ flexShrink: 0 }}>
          <Tooltip title="Minimize">
            <IconButton
              size="small"
              aria-label="Minimize onboarding checklist"
              onClick={() => setMinimized(true)}
            >
              <UnfoldLessRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          {detail.can_manage ? (
            <>
              <Tooltip title="Edit">
                <IconButton size="small" aria-label="Edit onboarding checklist" onClick={onEdit}>
                  <EditOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              {!detail.is_published ? (
                <Tooltip title="Publish">
                  <IconButton
                    size="small"
                    color="primary"
                    aria-label="Publish onboarding checklist"
                    onClick={onPublish}
                  >
                    <PublishRoundedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : null}
              {!detail.is_published ? (
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
              ) : null}
            </>
          ) : null}
          <Tooltip title="Close">
            <IconButton size="small" aria-label="Close onboarding checklist" onClick={onClose}>
              <CloseRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>

      <Stack
        direction="row"
        spacing={0.75}
        sx={{ mb: 0.75, alignItems: 'center', justifyContent: 'flex-end' }}
      >
        <ProsohmButton size="small" buttonVariant="secondary" onClick={expandAll}>
          Expand all
        </ProsohmButton>
        <ProsohmButton size="small" buttonVariant="secondary" onClick={collapseAll}>
          Collapse all
        </ProsohmButton>
      </Stack>

      <Stack spacing={0.75}>
        {[...bySection.entries()].map(([section, items]) => {
          const { done, total } = sectionStats(items);
          const open = expandedSections.has(section);
          return (
            <Box
              key={section}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                overflow: 'hidden',
              }}
            >
              <Box
                onClick={() => toggleSection(section)}
                sx={{
                  px: 1,
                  py: 0.55,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  cursor: 'pointer',
                  bgcolor: 'action.hover',
                  '&:hover': { bgcolor: 'action.selected' },
                }}
              >
                <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', minWidth: 0 }}>
                  {open ? (
                    <ExpandLessRoundedIcon sx={{ fontSize: 18 }} color="action" />
                  ) : (
                    <ExpandMoreRoundedIcon sx={{ fontSize: 18 }} color="action" />
                  )}
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      letterSpacing: '0.05em',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                    }}
                  >
                    {section}
                  </Typography>
                  <Chip
                    size="small"
                    label={`${done}/${total}`}
                    color={done === total && total > 0 ? 'success' : 'default'}
                    sx={{ height: 18, '& .MuiChip-label': { px: 0.6, fontSize: '0.68rem' } }}
                  />
                </Stack>
              </Box>
              <Collapse in={open} timeout="auto" unmountOnExit={false}>
                <Stack>
                  {items.map((item) => (
                    <Box
                      key={item.id}
                      sx={{
                        px: 1,
                        py: 0.4,
                        display: 'grid',
                        gridTemplateColumns: {
                          xs: '18px minmax(0, 1fr)',
                          sm: '18px minmax(0, 1fr) 112px',
                        },
                        columnGap: 0.75,
                        rowGap: 0.35,
                        alignItems: 'center',
                        borderTop: '1px solid',
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
                        <Box
                          sx={{
                            display: 'flex',
                            color: item.status === 'completed' ? 'success.main' : 'text.disabled',
                          }}
                        >
                          {item.status === 'completed' ? (
                            <CheckCircleOutlineRoundedIcon sx={{ fontSize: 16 }} />
                          ) : (
                            <RadioButtonUncheckedRoundedIcon sx={{ fontSize: 16 }} />
                          )}
                        </Box>
                      </Tooltip>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: 600, lineHeight: 1.25, fontSize: '0.8125rem' }}
                        >
                          {item.item_text}
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ display: 'block', lineHeight: 1.2 }}
                          noWrap
                        >
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
                      <Box
                        sx={{
                          gridColumn: { xs: '1 / -1', sm: 'auto' },
                          justifySelf: { xs: 'stretch', sm: 'end' },
                          pl: { xs: '26px', sm: 0 },
                        }}
                      >
                        {item.can_edit ? (
                          <TextField
                            select
                            size="small"
                            value={item.status}
                            disabled={busy}
                            onChange={(event) =>
                              onStatus(item.id, event.target.value as OnboardingItemStatus)
                            }
                            fullWidth
                            sx={{
                              minWidth: { sm: 112 },
                              maxWidth: { sm: 112 },
                              '& .MuiInputBase-root': { height: 28 },
                              '& .MuiSelect-select': { py: 0.5, fontSize: '0.75rem' },
                            }}
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
                    </Box>
                  ))}
                </Stack>
              </Collapse>
            </Box>
          );
        })}
      </Stack>
      </Box>
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
  const [employeeEmail, setEmployeeEmail] = useState('');
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
      setEmployeeEmail('');
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
      setEmployeeEmail('');
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
    if (mode === 'create' && !employeeUserId && !employeeEmail.trim()) return;
    const dept = departmentOptions.find((row) => row.id === departmentId);
    const codeLocked = mode === 'edit' && Boolean(initial?.employee_code);
    const joiningLocked = mode === 'edit' && Boolean(initial?.joining_date);
    const payload: FormPayload & { status?: 'in_progress' | 'completed' | 'cancelled' } = {
      employee_name: employeeName.trim(),
      employee_user_id: employeeUserId || null,
      employee_email: mode === 'create' && !employeeUserId ? employeeEmail.trim() || null : null,
      designation: designation.trim() || null,
      department_name: dept?.name ?? null,
      org_department_id: departmentId || null,
      team_id: teamId || null,
      role_id: roleId || null,
      reporting_manager_id: managerId || null,
      notes: notes.trim() || null,
    };
    if (!codeLocked) {
      payload.employee_code = employeeCode.trim() || null;
    }
    if (!joiningLocked) {
      payload.joining_date = joiningDate || null;
    }
    if (mode === 'edit') {
      payload.status = status;
    }
    onSubmit(payload);
  };

  const codeLocked = mode === 'edit' && Boolean(initial?.employee_code);
  const joiningLocked = mode === 'edit' && Boolean(initial?.joining_date);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" fullScreen={fullScreen}>
      <DialogTitle>
        {mode === 'edit' ? 'Edit onboarding' : 'Start onboarding'}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1.25} sx={{ mt: 1 }}>
          {mode === 'create' ? (
            <Typography variant="caption" color="text.secondary">
              Starting onboarding creates a User account when you enter an email (provisional Designer
              role, default password Prosohm@2026). The team leader is notified in-app and by email.
              Help Desk tickets are raised for HR, Admin, IT, and Accounts.
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
            <MenuItem value="">— Create new user via email —</MenuItem>
            {userOptions.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.name}
              </MenuItem>
            ))}
          </TextField>
          {mode === 'create' && !employeeUserId ? (
            <TextField
              required
              fullWidth
              size="small"
              type="email"
              label="Employee email"
              value={employeeEmail}
              onChange={(event) => setEmployeeEmail(event.target.value)}
              helperText="Required to create the User account when onboarding starts."
            />
          ) : null}
          <TextField
            required
            fullWidth
            size="small"
            label="Employee name"
            value={employeeName}
            onChange={(event) => setEmployeeName(event.target.value)}
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
            <Tooltip
              title={
                codeLocked
                  ? 'Employee ID is a historical identifier and cannot be changed here.'
                  : ''
              }
            >
              <TextField
                fullWidth
                size="small"
                label="Employee ID"
                value={employeeCode}
                onChange={(event) => {
                  if (codeLocked) return;
                  setEmployeeCode(event.target.value);
                }}
                placeholder="e.g. PP045"
                helperText={codeLocked ? 'Locked after first save.' : undefined}
                slotProps={{
                  input: codeLocked
                    ? {
                        readOnly: true,
                        startAdornment: (
                          <InputAdornment position="start">
                            <LockOutlinedIcon fontSize="small" />
                          </InputAdornment>
                        ),
                      }
                    : undefined,
                }}
              />
            </Tooltip>
            <Tooltip
              title={
                joiningLocked
                  ? 'Joining date is a historical fact. Correct it from Users → Correct historical dates if it was entered wrongly.'
                  : ''
              }
            >
              <TextField
                fullWidth
                size="small"
                type="date"
                label="Joining date"
                value={joiningDate}
                onChange={(event) => {
                  if (joiningLocked) return;
                  setJoiningDate(event.target.value);
                }}
                helperText={joiningLocked ? 'Locked after first save.' : undefined}
                slotProps={{
                  inputLabel: { shrink: true },
                  input: joiningLocked
                    ? {
                        readOnly: true,
                        startAdornment: (
                          <InputAdornment position="start">
                            <LockOutlinedIcon fontSize="small" />
                          </InputAdornment>
                        ),
                      }
                    : undefined,
                }}
              />
            </Tooltip>
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
          disabled={
            loading ||
            !employeeName.trim() ||
            (mode === 'create' && !employeeUserId && !employeeEmail.trim())
          }
        >
          {mode === 'edit' ? 'Save changes' : 'Create & route'}
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}
