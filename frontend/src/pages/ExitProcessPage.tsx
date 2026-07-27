import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ContentCard } from '../components/ui/cards';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { useToast } from '../context/ToastContext';
import { getErrorMessage } from '../api/client';
import {
  exitProcessApi,
  type ExitInterview,
  type ExitInterviewCreate,
  type ExitInterviewQuestion,
  type ExitInterviewStatus,
} from '../api/exitProcess';
import { usersApi } from '../api/resources';
import { fetchOrgDepartments, fetchRoles, fetchTeams } from '../api/lookups';
import { designTokens } from '../theme/designTokens';

const STATUS_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
];

const emptyCreate = (): ExitInterviewCreate => ({
  employee_name: '',
  employee_user_id: null,
  designation: '',
  department_name: '',
  last_working_date: '',
  resignation_date: '',
  interview_date: new Date().toISOString().slice(0, 10),
  notes: '',
  answers: {},
});

function statusColor(status: string): 'default' | 'info' | 'success' | 'warning' {
  if (status === 'completed') return 'success';
  if (status === 'in_progress') return 'info';
  if (status === 'draft') return 'warning';
  return 'default';
}

function groupQuestions(questions: ExitInterviewQuestion[]) {
  const sections: { section: string; items: ExitInterviewQuestion[] }[] = [];
  for (const q of questions) {
    const last = sections[sections.length - 1];
    if (!last || last.section !== q.section) {
      sections.push({ section: q.section, items: [q] });
    } else {
      last.items.push(q);
    }
  }
  return sections;
}

export default function ExitProcessPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<ExitInterviewCreate>(emptyCreate());
  const [deleteTarget, setDeleteTarget] = useState<ExitInterview | null>(null);
  const [publishTarget, setPublishTarget] = useState<ExitInterview | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | number>>({});
  const [meta, setMeta] = useState({
    last_working_date: '',
    resignation_date: '',
    interview_date: '',
    notes: '',
    status: 'draft' as ExitInterviewStatus,
  });

  const listQuery = useQuery({
    queryKey: ['exit-process', statusFilter],
    queryFn: () => exitProcessApi.list({ status: statusFilter }),
  });

  const detailQuery = useQuery({
    queryKey: ['exit-process', selectedId],
    queryFn: () => exitProcessApi.get(selectedId!),
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

  const selected = detailQuery.data;
  const questions = selected?.questions ?? [];
  const sections = useMemo(() => groupQuestions(questions), [questions]);

  useEffect(() => {
    if (!selected) return;
    setAnswers(selected.answers ?? {});
    setMeta({
      last_working_date: selected.last_working_date ?? '',
      resignation_date: selected.resignation_date ?? '',
      interview_date: selected.interview_date ?? '',
      notes: selected.notes ?? '',
      status: selected.status,
    });
  }, [selected]);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['exit-process'] });
  };

  const createMutation = useMutation({
    mutationFn: exitProcessApi.create,
    onSuccess: (data) => {
      showSuccess(`Exit interview started for ${data.employee_name}`);
      setCreateOpen(false);
      setCreateForm(emptyCreate());
      setSelectedId(data.id);
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not start exit interview'),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      exitProcessApi.update(selectedId!, {
        ...meta,
        last_working_date: meta.last_working_date || null,
        resignation_date: meta.resignation_date || null,
        interview_date: meta.interview_date || null,
        answers,
      }),
    onSuccess: () => {
      showSuccess('Exit interview saved');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not save exit interview'),
  });

  const completeMutation = useMutation({
    mutationFn: () =>
      exitProcessApi.update(selectedId!, {
        ...meta,
        last_working_date: meta.last_working_date || null,
        resignation_date: meta.resignation_date || null,
        interview_date: meta.interview_date || null,
        answers,
        status: 'completed',
      }),
    onSuccess: () => {
      showSuccess('Exit interview marked completed');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not complete exit interview'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => exitProcessApi.remove(id),
    onSuccess: () => {
      showSuccess('Exit interview removed');
      if (deleteTarget && selectedId === deleteTarget.id) setSelectedId(null);
      setDeleteTarget(null);
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not delete exit interview'),
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => exitProcessApi.publish(id),
    onSuccess: (data) => {
      showSuccess(`Exit interview published for ${data.employee_name}`);
      setPublishTarget(null);
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ['exit-process', data.id] });
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not publish exit interview'),
  });

  const users = usersQuery.data ?? [];
  const departments = departmentsQuery.data ?? [];
  const teams = teamsQuery.data ?? [];
  const roles = rolesQuery.data ?? [];

  const onPickEmployee = (userId: string) => {
    const user = users.find((u) => u.id === userId);
    if (!user) {
      setCreateForm((prev) => ({ ...prev, employee_user_id: userId || null }));
      return;
    }
    setCreateForm((prev) => ({
      ...prev,
      employee_user_id: user.id,
      employee_name: `${user.first_name} ${user.last_name}`.trim(),
      designation: user.designation ?? prev.designation,
      reporting_manager_id: user.manager_id ?? prev.reporting_manager_id,
    }));
  };

  if (listQuery.isLoading) {
    return <LoadingState message="Loading exit process…" />;
  }

  return (
    <PageContainer>
      <PageHeader
        subtitle="Generic employee exit interview (PP-HRD-FO-30) — start a form for any departing employee."
        action={
          <ProsohmButton
            buttonVariant="primary"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Start exit interview
          </ProsohmButton>
        }
      />

      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', gap: 1 }}>
        {STATUS_FILTERS.map((row) => (
          <Chip
            key={row.value}
            label={row.label}
            color={statusFilter === row.value ? 'primary' : 'default'}
            variant={statusFilter === row.value ? 'filled' : 'outlined'}
            onClick={() => setStatusFilter(row.value)}
          />
        ))}
      </Stack>

      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={2}
        sx={{ alignItems: 'flex-start' }}
      >
        <Box sx={{ width: { xs: '100%', md: 360 }, flexShrink: 0 }}>
          <Stack spacing={1.25}>
            {(listQuery.data ?? []).length === 0 ? (
              <ContentCard>
                <Typography variant="body2" color="text.secondary">
                  No exit interviews yet. Start one for a departing employee.
                </Typography>
              </ContentCard>
            ) : (
              (listQuery.data ?? []).map((row) => (
                <Card
                  key={row.id}
                  variant="outlined"
                  sx={{
                    borderColor: selectedId === row.id ? 'primary.main' : 'divider',
                    borderWidth: selectedId === row.id ? 2 : 1,
                    borderRadius: `${designTokens.radius.md}px`,
                  }}
                >
                  <CardActionArea onClick={() => setSelectedId(row.id)}>
                    <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                      <Stack
                        direction="row"
                        spacing={1}
                        sx={{ justifyContent: 'space-between' }}
                      >
                        <Box>
                          <Typography sx={{ fontWeight: 700 }}>{row.employee_name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {[row.designation, row.department_name || row.team_name]
                              .filter(Boolean)
                              .join(' · ') || 'Exit interview'}
                          </Typography>
                        </Box>
                        <Stack spacing={0.5} sx={{ alignItems: 'flex-end' }}>
                          <Chip size="small" color={statusColor(row.status)} label={row.status_label} />
                          {row.is_published ? (
                            <Chip size="small" color="success" variant="outlined" label="Published" />
                          ) : null}
                        </Stack>
                      </Stack>
                    </CardContent>
                  </CardActionArea>
                </Card>
              ))
            )}
          </Stack>
        </Box>

        <Box sx={{ flex: 1, minWidth: 0, width: '100%' }}>
          {!selectedId ? (
            <ContentCard>
              <Typography variant="body2" color="text.secondary">
                Select an exit interview from the list, or start a new one.
              </Typography>
            </ContentCard>
          ) : detailQuery.isLoading || !selected ? (
            <LoadingState message="Loading interview…" />
          ) : (
            <ContentCard>
              <Stack spacing={2}>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={1}
                  sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' } }}
                >
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>
                      {selected.employee_name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {selected.form_code} · {selected.form_title}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <Chip size="small" color={statusColor(selected.status)} label={selected.status_label} />
                    {selected.is_published ? (
                      <Chip size="small" color="success" variant="outlined" label="Published" />
                    ) : null}
                    {!selected.is_published ? (
                      <ProsohmButton
                        size="small"
                        buttonVariant="primary"
                        onClick={() => setPublishTarget(selected)}
                      >
                        Publish
                      </ProsohmButton>
                    ) : null}
                    {!selected.is_published ? (
                      <ProsohmButton
                        size="small"
                        buttonVariant="danger"
                        startIcon={<DeleteOutlineRoundedIcon />}
                        onClick={() => setDeleteTarget(selected)}
                      >
                        Delete
                      </ProsohmButton>
                    ) : null}
                  </Stack>
                </Stack>

                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                  <TextField
                    size="small"
                    type="date"
                    label="Resignation date"
                    value={meta.resignation_date}
                    onChange={(e) => setMeta((p) => ({ ...p, resignation_date: e.target.value }))}
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ minWidth: 160 }}
                  />
                  <TextField
                    size="small"
                    type="date"
                    label="Last working day"
                    value={meta.last_working_date}
                    onChange={(e) => setMeta((p) => ({ ...p, last_working_date: e.target.value }))}
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ minWidth: 160 }}
                  />
                  <TextField
                    size="small"
                    type="date"
                    label="Interview date"
                    value={meta.interview_date}
                    onChange={(e) => setMeta((p) => ({ ...p, interview_date: e.target.value }))}
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ minWidth: 160 }}
                  />
                  <TextField
                    size="small"
                    select
                    label="Status"
                    value={meta.status}
                    onChange={(e) =>
                      setMeta((p) => ({ ...p, status: e.target.value as ExitInterviewStatus }))
                    }
                    sx={{ minWidth: 140 }}
                  >
                    <MenuItem value="draft">Draft</MenuItem>
                    <MenuItem value="in_progress">In progress</MenuItem>
                    <MenuItem value="completed">Completed</MenuItem>
                    <MenuItem value="cancelled">Cancelled</MenuItem>
                  </TextField>
                </Stack>

                <Divider />

                {sections.map((section) => (
                  <Box key={section.section}>
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: 700, mb: 1.25, color: 'text.secondary' }}
                    >
                      {section.section}
                    </Typography>
                    <Stack spacing={1.5}>
                      {section.items.map((q) => (
                        <Box key={q.id}>
                          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.75 }}>
                            {q.prompt}
                            {q.required ? ' *' : ''}
                          </Typography>
                          {q.input === 'choice' ? (
                            <TextField
                              select
                              size="small"
                              fullWidth
                              value={answers[q.id] ?? ''}
                              onChange={(e) =>
                                setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                              }
                            >
                              <MenuItem value="">—</MenuItem>
                              {q.options.map((opt) => (
                                <MenuItem key={opt} value={opt}>
                                  {opt}
                                </MenuItem>
                              ))}
                            </TextField>
                          ) : q.input === 'rating' ? (
                            <TextField
                              select
                              size="small"
                              sx={{ width: 120 }}
                              value={answers[q.id] ?? ''}
                              onChange={(e) =>
                                setAnswers((prev) => ({
                                  ...prev,
                                  [q.id]: e.target.value ? Number(e.target.value) : '',
                                }))
                              }
                            >
                              <MenuItem value="">—</MenuItem>
                              {Array.from(
                                { length: (q.max ?? 5) - (q.min ?? 1) + 1 },
                                (_, i) => (q.min ?? 1) + i,
                              ).map((n) => (
                                <MenuItem key={n} value={n}>
                                  {n}
                                </MenuItem>
                              ))}
                            </TextField>
                          ) : (
                            <TextField
                              size="small"
                              fullWidth
                              multiline={q.input === 'textarea'}
                              minRows={q.input === 'textarea' ? 3 : 1}
                              value={answers[q.id] ?? ''}
                              onChange={(e) =>
                                setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                              }
                            />
                          )}
                        </Box>
                      ))}
                    </Stack>
                  </Box>
                ))}

                <TextField
                  size="small"
                  label="HR notes"
                  fullWidth
                  multiline
                  minRows={2}
                  value={meta.notes}
                  onChange={(e) => setMeta((p) => ({ ...p, notes: e.target.value }))}
                />

                <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                  <ProsohmButton
                    buttonVariant="outlined"
                    disabled={saveMutation.isPending}
                    onClick={() => saveMutation.mutate()}
                  >
                    Save
                  </ProsohmButton>
                  <ProsohmButton
                    buttonVariant="primary"
                    disabled={completeMutation.isPending}
                    onClick={() => completeMutation.mutate()}
                  >
                    Mark completed
                  </ProsohmButton>
                </Stack>
              </Stack>
            </ContentCard>
          )}
        </Box>
      </Stack>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Start exit interview</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            <TextField
              select
              size="small"
              label="Employee (optional lookup)"
              value={createForm.employee_user_id ?? ''}
              onChange={(e) => onPickEmployee(e.target.value)}
              fullWidth
            >
              <MenuItem value="">Manual entry</MenuItem>
              {users.map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {u.first_name} {u.last_name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              size="small"
              label="Employee name"
              required
              value={createForm.employee_name}
              onChange={(e) => setCreateForm((p) => ({ ...p, employee_name: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Designation"
              value={createForm.designation ?? ''}
              onChange={(e) => setCreateForm((p) => ({ ...p, designation: e.target.value }))}
              fullWidth
            />
            <TextField
              select
              size="small"
              label="Department"
              value={createForm.org_department_id ?? ''}
              onChange={(e) => {
                const id = e.target.value || null;
                const dept = departments.find((d) => d.id === id);
                setCreateForm((p) => ({
                  ...p,
                  org_department_id: id,
                  department_name: dept?.name ?? p.department_name,
                }));
              }}
              fullWidth
            >
              <MenuItem value="">—</MenuItem>
              {departments.map((d) => (
                <MenuItem key={d.id} value={d.id}>
                  {d.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Team"
              value={createForm.team_id ?? ''}
              onChange={(e) =>
                setCreateForm((p) => ({ ...p, team_id: e.target.value || null }))
              }
              fullWidth
            >
              <MenuItem value="">—</MenuItem>
              {teams.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Role"
              value={createForm.role_id ?? ''}
              onChange={(e) =>
                setCreateForm((p) => ({ ...p, role_id: e.target.value || null }))
              }
              fullWidth
            >
              <MenuItem value="">—</MenuItem>
              {roles.map((r) => (
                <MenuItem key={r.id} value={r.id}>
                  {r.name}
                </MenuItem>
              ))}
            </TextField>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <TextField
                size="small"
                type="date"
                label="Resignation date"
                value={createForm.resignation_date ?? ''}
                onChange={(e) =>
                  setCreateForm((p) => ({ ...p, resignation_date: e.target.value }))
                }
                slotProps={{ inputLabel: { shrink: true } }}
                fullWidth
              />
              <TextField
                size="small"
                type="date"
                label="Last working day"
                value={createForm.last_working_date ?? ''}
                onChange={(e) =>
                  setCreateForm((p) => ({ ...p, last_working_date: e.target.value }))
                }
                slotProps={{ inputLabel: { shrink: true } }}
                fullWidth
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <ProsohmButton buttonVariant="outlined" onClick={() => setCreateOpen(false)}>
            Cancel
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            disabled={!createForm.employee_name.trim() || createMutation.isPending}
            onClick={() =>
              createMutation.mutate({
                ...createForm,
                employee_name: createForm.employee_name.trim(),
                resignation_date: createForm.resignation_date || null,
                last_working_date: createForm.last_working_date || null,
                interview_date: createForm.interview_date || null,
              })
            }
          >
            Start
          </ProsohmButton>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete exit interview?"
        message="This permanently removes the exit interview and answers."
        recordName={deleteTarget?.employee_name}
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />

      <ConfirmDialog
        open={Boolean(publishTarget)}
        title="Publish exit interview?"
        message="Publishing locks this exit interview as the official record. After publish, it cannot be deleted."
        recordName={publishTarget?.employee_name}
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
