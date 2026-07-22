import { useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ContentCard } from '../components/ui/cards';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useToast } from '../context/ToastContext';
import { getErrorMessage } from '../api/client';
import {
  onboardingApi,
  type OnboardingChecklist,
  type OnboardingChecklistDetail,
  type OnboardingItemStatus,
} from '../api/onboarding';
import { usersApi } from '../api/resources';

const STATUS_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
];

export default function OnboardingPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('in_progress');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

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

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['onboarding'] });
  };

  const createMutation = useMutation({
    mutationFn: onboardingApi.create,
    onSuccess: (data) => {
      showSuccess(`Onboarding started for ${data.employee_name}.`);
      setCreateOpen(false);
      setSelectedId(data.id);
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
      showSuccess('Checklist item updated.');
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ['onboarding', selectedId] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const rows = listQuery.data ?? [];
  const detail = detailQuery.data;

  return (
    <PageContainer>
      <PageHeader
        title="Onboarding"
        subtitle="New-hire checklist (PP-HRD-FO-14) — Human Resources, Engineering, IT, and Accounts."
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

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          sx={{ minWidth: 180 }}
        >
          {STATUS_FILTERS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>
      </Stack>

      {listQuery.isLoading ? (
        <LoadingState message="Loading onboarding checklists…" />
      ) : rows.length === 0 ? (
        <ContentCard>
          <Typography color="text.secondary">
            No onboarding checklists yet. Start one when a new hire joins.
          </Typography>
        </ContentCard>
      ) : (
        <Stack spacing={1.25}>
          {rows.map((row) => (
            <ChecklistRow
              key={row.id}
              row={row}
              selected={selectedId === row.id}
              onOpen={() => setSelectedId(row.id)}
            />
          ))}
        </Stack>
      )}

      {selectedId ? (
        <Box sx={{ mt: 3 }}>
          {detailQuery.isLoading || !detail ? (
            <LoadingState message="Loading checklist…" />
          ) : (
            <ChecklistDetail
              detail={detail}
              busy={itemMutation.isPending}
              onStatus={(itemId, status) => itemMutation.mutate({ itemId, status })}
              onClose={() => setSelectedId(null)}
            />
          )}
        </Box>
      ) : null}

      <CreateOnboardingDialog
        open={createOpen}
        users={usersQuery.data ?? []}
        loading={createMutation.isPending}
        onClose={() => setCreateOpen(false)}
        onSubmit={(payload) => createMutation.mutate(payload)}
      />
    </PageContainer>
  );
}

function ChecklistRow({
  row,
  selected,
  onOpen,
}: {
  row: OnboardingChecklist;
  selected: boolean;
  onOpen: () => void;
}) {
  return (
    <ContentCard noPadding>
      <Box
        onClick={onOpen}
        sx={{
          px: 2,
          py: 1.5,
          cursor: 'pointer',
          borderLeft: selected ? '4px solid' : '4px solid transparent',
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
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <HowToRegRoundedIcon fontSize="small" color="primary" />
              <Typography sx={{ fontWeight: 800 }}>{row.employee_name}</Typography>
              {row.employee_code ? (
                <Chip size="small" variant="outlined" label={row.employee_code} />
              ) : null}
              <Chip size="small" label={row.status_label} color={row.status === 'completed' ? 'success' : 'info'} />
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {[row.designation, row.department_name, row.joining_date ? `Joined ${row.joining_date}` : null]
                .filter(Boolean)
                .join(' · ') || 'New hire'}
              {row.reporting_manager_name ? ` · Manager: ${row.reporting_manager_name}` : ''}
            </Typography>
            <Box sx={{ mt: 1, maxWidth: 360 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  {row.completed_items}/{row.total_items} complete
                </Typography>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>
                  {row.completion_percent}%
                </Typography>
              </Stack>
              <LinearProgress variant="determinate" value={row.completion_percent} />
            </Box>
          </Box>
        </Stack>
      </Box>
    </ContentCard>
  );
}

function ChecklistDetail({
  detail,
  busy,
  onStatus,
  onClose,
}: {
  detail: OnboardingChecklistDetail;
  busy: boolean;
  onStatus: (itemId: string, status: OnboardingItemStatus) => void;
  onClose: () => void;
}) {
  const bySection = useMemo(() => {
    const map = new Map<string, typeof detail.items>();
    for (const section of detail.sections) {
      map.set(
        section,
        detail.items.filter((item) => item.section === section),
      );
    }
    return map;
  }, [detail]);

  return (
    <ContentCard>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1}
        sx={{ mb: 2, alignItems: { sm: 'flex-start' }, justifyContent: 'space-between' }}
      >
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>
            {detail.employee_name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {detail.template_code ?? 'PP-HRD-FO-14'} · {detail.completion_percent}% complete
            {detail.reporting_manager_name ? ` · Manager: ${detail.reporting_manager_name}` : ''}
          </Typography>
        </Box>
        <ProsohmButton buttonVariant="secondary" onClick={onClose}>
          Close
        </ProsohmButton>
      </Stack>

      <Stack spacing={2.5}>
        {[...bySection.entries()].map(([section, items]) => (
          <Box key={section}>
            <Typography
              variant="overline"
              sx={{ color: 'text.secondary', letterSpacing: '0.08em', fontWeight: 700 }}
            >
              {section}
            </Typography>
            <Stack spacing={1} sx={{ mt: 0.75 }}>
              {items.map((item, index) => (
                <Box
                  key={item.id}
                  sx={{
                    p: 1.25,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    display: 'flex',
                    gap: 1.5,
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ minWidth: 24, pt: 0.5, fontWeight: 700 }}
                  >
                    {index + 1}
                  </Typography>
                  <Box sx={{ flex: '1 1 220px', minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {item.item_text}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.responsibility_label}
                      {item.completed_by_name
                        ? ` · ${item.completed_by_name}${item.completion_date ? ` · ${item.completion_date}` : ''}`
                        : ''}
                    </Typography>
                  </Box>
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
                  />
                  {item.can_edit ? (
                    <TextField
                      select
                      size="small"
                      label="Update"
                      value={item.status}
                      disabled={busy}
                      onChange={(event) =>
                        onStatus(item.id, event.target.value as OnboardingItemStatus)
                      }
                      sx={{ minWidth: 150 }}
                    >
                      <MenuItem value="pending">Pending</MenuItem>
                      <MenuItem value="completed">Completed</MenuItem>
                      <MenuItem value="not_applicable">N/A</MenuItem>
                    </TextField>
                  ) : null}
                </Box>
              ))}
            </Stack>
          </Box>
        ))}
      </Stack>
    </ContentCard>
  );
}

function CreateOnboardingDialog({
  open,
  users,
  loading,
  onClose,
  onSubmit,
}: {
  open: boolean;
  users: Array<{
    id: string;
    first_name: string;
    last_name: string;
    designation?: string | null;
  }>;
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    employee_name: string;
    employee_user_id?: string | null;
    employee_code?: string | null;
    joining_date?: string | null;
    designation?: string | null;
    department_name?: string | null;
    reporting_manager_id?: string | null;
    notes?: string | null;
  }) => void;
}) {
  const [employeeUserId, setEmployeeUserId] = useState('');
  const [employeeName, setEmployeeName] = useState('');
  const [employeeCode, setEmployeeCode] = useState('');
  const [joiningDate, setJoiningDate] = useState('');
  const [designation, setDesignation] = useState('');
  const [departmentName, setDepartmentName] = useState('Prosohm');
  const [managerId, setManagerId] = useState('');
  const [notes, setNotes] = useState('');

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

  const handleEmployeePick = (id: string) => {
    setEmployeeUserId(id);
    const match = userOptions.find((user) => user.id === id);
    if (match) {
      setEmployeeName(match.name);
      if (match.designation) setDesignation(match.designation);
    }
  };

  const handleSubmit = () => {
    if (!employeeName.trim()) return;
    onSubmit({
      employee_name: employeeName.trim(),
      employee_user_id: employeeUserId || null,
      employee_code: employeeCode.trim() || null,
      joining_date: joiningDate || null,
      designation: designation.trim() || null,
      department_name: departmentName.trim() || null,
      reporting_manager_id: managerId || null,
      notes: notes.trim() || null,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Start onboarding (PP-HRD-FO-14)</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
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
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
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
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              fullWidth
              size="small"
              label="Designation"
              value={designation}
              onChange={(event) => setDesignation(event.target.value)}
            />
            <TextField
              fullWidth
              size="small"
              label="Department"
              value={departmentName}
              onChange={(event) => setDepartmentName(event.target.value)}
            />
          </Stack>
          <TextField
            select
            fullWidth
            size="small"
            label="Reporting manager"
            value={managerId}
            onChange={(event) => setManagerId(event.target.value)}
          >
            <MenuItem value="">— Select —</MenuItem>
            {userOptions.map((user) => (
              <MenuItem key={user.id} value={user.id}>
                {user.name}
              </MenuItem>
            ))}
          </TextField>
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
          Create checklist
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}
