import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import CancelRoundedIcon from '@mui/icons-material/CancelRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { fetchUsers, fetchWorkingModels } from '../../api/lookups';
import { rolesApi } from '../../api/resources';
import {
  actOnCompensationRequest,
  createCompensationRequest,
  fetchCompensationRequests,
  type CompensationChangeRequest,
} from '../../api/compensationRequests';

const STAGE_META: Record<string, { label: string; color: 'default' | 'info' | 'warning' | 'success' | 'error' }> = {
  suggested: { label: 'Suggested', color: 'warning' },
  l1_approved: { label: 'L1 approved', color: 'info' },
  l2_approved: { label: 'Approved (pending date)', color: 'info' },
  applied: { label: 'Applied', color: 'success' },
  rejected: { label: 'Rejected', color: 'error' },
};

function fmtMoney(value: number | string | null | undefined, currency: string): string {
  if (value == null || value === '') return '—';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return `${currency} ${num.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

type Props = {
  canManage: boolean;
};

export function CompensationApprovalsPanel({ canManage }: Props) {
  const theme = useTheme();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [employeeId, setEmployeeId] = useState('');
  const [requestType, setRequestType] = useState<'hike' | 'promotion'>('hike');
  const [hikePct, setHikePct] = useState('');
  const [effectiveDate, setEffectiveDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [justification, setJustification] = useState('');
  const [newRoleId, setNewRoleId] = useState('');
  const [newDesignation, setNewDesignation] = useState('');
  const [newWorkingModelId, setNewWorkingModelId] = useState('');

  const requestsQuery = useQuery({
    queryKey: ['compensation-requests'],
    queryFn: () => fetchCompensationRequests(),
  });
  const usersQuery = useQuery({ queryKey: ['lookup', 'users'], queryFn: fetchUsers });
  const rolesQuery = useQuery({ queryKey: ['roles'], queryFn: () => rolesApi.list() });
  const workingModelsQuery = useQuery({
    queryKey: ['lookup', 'working-models'],
    queryFn: fetchWorkingModels,
  });

  const users = usersQuery.data ?? [];
  const roles = rolesQuery.data ?? [];
  const workingModels = workingModelsQuery.data ?? [];

  const resetForm = () => {
    setEmployeeId('');
    setRequestType('hike');
    setHikePct('');
    setJustification('');
    setNewRoleId('');
    setNewDesignation('');
    setNewWorkingModelId('');
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createCompensationRequest({
        user_id: employeeId,
        request_type: requestType,
        hike_pct: hikePct ? Number(hikePct) : null,
        effective_date: effectiveDate,
        justification: justification || null,
        new_role_id: requestType === 'promotion' && newRoleId ? newRoleId : null,
        new_designation: requestType === 'promotion' && newDesignation ? newDesignation : null,
        new_working_model_id: newWorkingModelId || null,
      }),
    onSuccess: () => {
      showSuccess('Suggestion submitted for approval');
      resetForm();
      void queryClient.invalidateQueries({ queryKey: ['compensation-requests'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const actionMutation = useMutation({
    mutationFn: (vars: {
      id: string;
      action: 'approve-l1' | 'approve-l2' | 'reject' | 'withdraw';
      rejection_reason?: string;
    }) =>
      actOnCompensationRequest(vars.id, {
        action: vars.action,
        rejection_reason: vars.rejection_reason ?? null,
      }),
    onSuccess: () => {
      showSuccess('Request updated');
      void queryClient.invalidateQueries({ queryKey: ['compensation-requests'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const requests = requestsQuery.data ?? [];
  const pending = useMemo(
    () => requests.filter((r) => r.stage !== 'applied' && r.stage !== 'rejected'),
    [requests],
  );
  const history = useMemo(
    () => requests.filter((r) => r.stage === 'applied' || r.stage === 'rejected'),
    [requests],
  );

  if (requestsQuery.isLoading) {
    return <LoadingState message="Loading compensation requests…" />;
  }

  const canSuggest = canManage;

  return (
    <Stack spacing={2.5}>
      {canSuggest ? (
        <Box
          sx={{
            borderRadius: 2,
            p: 2,
            border: 1,
            borderColor: 'divider',
            background: `linear-gradient(135deg, ${alpha(theme.palette.success.main, 0.06)} 0%, ${alpha(
              theme.palette.background.paper,
              0.9,
            )} 60%)`,
          }}
        >
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1.5 }}>
            <TrendingUpRoundedIcon color="success" />
            <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
              Suggest a hike or promotion
            </Typography>
          </Stack>
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, md: 4 }}>
              <FilterSelect
                label="Employee"
                value={employeeId}
                onChange={(e) => setEmployeeId(String(e.target.value))}
              >
                <MenuItem value="">Select employee</MenuItem>
                {users
                  .filter((u) => u.is_active !== false)
                  .map((u) => (
                    <MenuItem key={u.id} value={u.id}>
                      {[u.first_name, u.last_name].filter(Boolean).join(' ') || u.email}
                    </MenuItem>
                  ))}
              </FilterSelect>
            </Grid>
            <Grid size={{ xs: 6, md: 2 }}>
              <FilterSelect
                label="Type"
                value={requestType}
                onChange={(e) => setRequestType(e.target.value as 'hike' | 'promotion')}
              >
                <MenuItem value="hike">Hike</MenuItem>
                <MenuItem value="promotion">Promotion</MenuItem>
              </FilterSelect>
            </Grid>
            <Grid size={{ xs: 6, md: 2 }}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label="Hike %"
                value={hikePct}
                onChange={(e) => setHikePct(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 6, md: 2 }}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="Effective date"
                slotProps={{ inputLabel: { shrink: true } }}
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
              />
            </Grid>
            {requestType === 'promotion' ? (
              <>
                <Grid size={{ xs: 6, md: 3 }}>
                  <FilterSelect
                    label="New role"
                    value={newRoleId}
                    onChange={(e) => setNewRoleId(String(e.target.value))}
                  >
                    <MenuItem value="">No role change</MenuItem>
                    {roles.map((r) => (
                      <MenuItem key={r.id} value={r.id}>
                        {r.name}
                      </MenuItem>
                    ))}
                  </FilterSelect>
                </Grid>
                <Grid size={{ xs: 6, md: 3 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label="New designation"
                    value={newDesignation}
                    onChange={(e) => setNewDesignation(e.target.value)}
                  />
                </Grid>
              </>
            ) : null}
            <Grid size={{ xs: 6, md: 3 }}>
              <FilterSelect
                label="Billing / working model"
                value={newWorkingModelId}
                onChange={(e) => setNewWorkingModelId(String(e.target.value))}
              >
                <MenuItem value="">No billing change</MenuItem>
                {workingModels.map((w) => (
                  <MenuItem key={w.id} value={w.id}>
                    {w.name}
                  </MenuItem>
                ))}
              </FilterSelect>
            </Grid>
            <Grid size={{ xs: 12, md: 9 }}>
              <TextField
                fullWidth
                size="small"
                label="Justification"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Button
                fullWidth
                variant="contained"
                color="success"
                disabled={!employeeId || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                Submit suggestion
              </Button>
            </Grid>
          </Grid>
        </Box>
      ) : null}

      <Box>
        <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
          Pending approvals
        </Typography>
        {pending.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No pending compensation requests.
          </Typography>
        ) : (
          <Stack spacing={1.25}>
            {pending.map((request) => (
              <RequestCard
                key={request.id}
                request={request}
                onAction={(action, reason) =>
                  actionMutation.mutate({ id: request.id, action, rejection_reason: reason })
                }
                busy={actionMutation.isPending}
              />
            ))}
          </Stack>
        )}
      </Box>

      {history.length > 0 ? (
        <Box>
          <Divider sx={{ mb: 1.5 }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
            History
          </Typography>
          <Stack spacing={1.25}>
            {history.map((request) => (
              <RequestCard key={request.id} request={request} onAction={() => {}} busy readOnly />
            ))}
          </Stack>
        </Box>
      ) : null}
    </Stack>
  );
}

function RequestCard({
  request,
  onAction,
  busy,
  readOnly,
}: {
  request: CompensationChangeRequest;
  onAction: (action: 'approve-l1' | 'approve-l2' | 'reject' | 'withdraw', reason?: string) => void;
  busy: boolean;
  readOnly?: boolean;
}) {
  const stage = STAGE_META[request.stage] ?? { label: request.stage, color: 'default' as const };
  const currency = request.currency_code || 'INR';

  return (
    <Box sx={{ borderRadius: 2, p: 1.75, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1}
        sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}
      >
        <Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
              {request.employee_name ?? 'Employee'}
            </Typography>
            <Chip size="small" label={request.request_type === 'promotion' ? 'Promotion' : 'Hike'} />
            <Chip size="small" color={stage.color} label={stage.label} />
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
            {request.hike_pct ? `+${request.hike_pct}% · ` : ''}
            {fmtMoney(request.current_monthly_salary, currency)} →{' '}
            {fmtMoney(request.proposed_monthly_salary, currency)} · effective {request.effective_date}
          </Typography>
          {request.new_role_name || request.new_designation ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              Promotion: {request.new_role_name ?? request.new_designation}
            </Typography>
          ) : null}
          {request.new_working_model_name ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              Billing → {request.new_working_model_name}
            </Typography>
          ) : null}
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            Suggested by {request.suggested_by_name ?? '—'}
            {request.l1_approver_name ? ` · L1: ${request.l1_approver_name}` : ''}
            {request.l2_approver_name ? ` · L2: ${request.l2_approver_name}` : ''}
          </Typography>
          {request.justification ? (
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              {request.justification}
            </Typography>
          ) : null}
          {request.rejection_reason ? (
            <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
              {request.rejection_reason}
            </Typography>
          ) : null}
        </Box>
        {!readOnly ? (
          <Stack direction="row" spacing={0.75} sx={{ flexShrink: 0 }}>
            {request.can_approve_l1 ? (
              <Button
                size="small"
                variant="contained"
                startIcon={<CheckCircleRoundedIcon />}
                disabled={busy}
                onClick={() => onAction('approve-l1')}
              >
                Approve L1
              </Button>
            ) : null}
            {request.can_approve_l2 ? (
              <Button
                size="small"
                variant="contained"
                color="success"
                startIcon={<CheckCircleRoundedIcon />}
                disabled={busy}
                onClick={() => onAction('approve-l2')}
              >
                Approve L2
              </Button>
            ) : null}
            {(request.can_approve_l1 || request.can_approve_l2) ? (
              <Button
                size="small"
                color="error"
                startIcon={<CancelRoundedIcon />}
                disabled={busy}
                onClick={() => onAction('reject', 'Rejected')}
              >
                Reject
              </Button>
            ) : null}
            {request.can_withdraw ? (
              <Button size="small" color="inherit" disabled={busy} onClick={() => onAction('withdraw')}>
                Withdraw
              </Button>
            ) : null}
          </Stack>
        ) : null}
      </Stack>
    </Box>
  );
}

export default CompensationApprovalsPanel;
