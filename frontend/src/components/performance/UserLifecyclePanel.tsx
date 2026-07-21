import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded';
import WorkspacePremiumRoundedIcon from '@mui/icons-material/WorkspacePremiumRounded';
import PaidRoundedIcon from '@mui/icons-material/PaidRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { fetchTeams, fetchUsers, fetchWorkingModels } from '../../api/lookups';
import { rolesApi } from '../../api/resources';
import {
  changeUserBilling,
  fetchUserLifecycle,
  promoteUser,
  transferUser,
} from '../../api/compensationRequests';

const EVENT_LABEL: Record<string, string> = {
  transfer: 'Transfer',
  promotion: 'Promotion',
  billing_change: 'Billing change',
  hike: 'Hike',
};

type ActionKind = 'transfer' | 'promote' | 'billing';

export function UserLifecyclePanel({ canManage }: { canManage: boolean }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [employeeId, setEmployeeId] = useState('');
  const [action, setAction] = useState<ActionKind>('transfer');
  const [effectiveDate, setEffectiveDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [targetTeamId, setTargetTeamId] = useState('');
  const [newRoleId, setNewRoleId] = useState('');
  const [newDesignation, setNewDesignation] = useState('');
  const [newWorkingModelId, setNewWorkingModelId] = useState('');

  const usersQuery = useQuery({ queryKey: ['lookup', 'users'], queryFn: fetchUsers });
  const teamsQuery = useQuery({ queryKey: ['lookup', 'teams'], queryFn: fetchTeams });
  const rolesQuery = useQuery({ queryKey: ['roles'], queryFn: () => rolesApi.list() });
  const workingModelsQuery = useQuery({
    queryKey: ['lookup', 'working-models'],
    queryFn: fetchWorkingModels,
  });
  const historyQuery = useQuery({
    queryKey: ['user-lifecycle', employeeId],
    queryFn: () => fetchUserLifecycle(employeeId),
    enabled: Boolean(employeeId),
  });

  const users = usersQuery.data ?? [];
  const teams = teamsQuery.data ?? [];
  const roles = rolesQuery.data ?? [];
  const workingModels = workingModelsQuery.data ?? [];

  const mutation = useMutation({
    mutationFn: async () => {
      if (!employeeId) return;
      if (action === 'transfer') {
        await transferUser(employeeId, {
          target_team_id: targetTeamId,
          effective_date: effectiveDate,
        });
      } else if (action === 'promote') {
        await promoteUser(employeeId, {
          new_role_id: newRoleId || null,
          new_designation: newDesignation || null,
          effective_date: effectiveDate,
        });
      } else {
        await changeUserBilling(employeeId, {
          new_working_model_id: newWorkingModelId || null,
          effective_date: effectiveDate,
        });
      }
    },
    onSuccess: () => {
      showSuccess('Lifecycle change recorded');
      void queryClient.invalidateQueries({ queryKey: ['user-lifecycle', employeeId] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const disabled = useMemo(() => {
    if (!employeeId || mutation.isPending) return true;
    if (action === 'transfer') return !targetTeamId;
    if (action === 'promote') return !newRoleId && !newDesignation;
    return false;
  }, [action, employeeId, mutation.isPending, newRoleId, newDesignation, targetTeamId]);

  return (
    <Stack spacing={2}>
      <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
        Lifecycle changes
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Record dated transfers, promotions, and billing (working-model) changes. Future-dated
        changes apply automatically on their effective date.
      </Typography>

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
        {canManage ? (
          <>
            <Grid size={{ xs: 6, md: 3 }}>
              <FilterSelect
                label="Action"
                value={action}
                onChange={(e) => setAction(e.target.value as ActionKind)}
              >
                <MenuItem value="transfer">Transfer team</MenuItem>
                <MenuItem value="promote">Promote</MenuItem>
                <MenuItem value="billing">Change billing</MenuItem>
              </FilterSelect>
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
            {action === 'transfer' ? (
              <Grid size={{ xs: 12, md: 3 }}>
                <FilterSelect
                  label="Target team"
                  value={targetTeamId}
                  onChange={(e) => setTargetTeamId(String(e.target.value))}
                >
                  <MenuItem value="">Select team</MenuItem>
                  {teams.map((t) => (
                    <MenuItem key={t.id} value={t.id}>
                      {t.name}
                    </MenuItem>
                  ))}
                </FilterSelect>
              </Grid>
            ) : null}
            {action === 'promote' ? (
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
            {action === 'billing' ? (
              <Grid size={{ xs: 12, md: 3 }}>
                <FilterSelect
                  label="Working model"
                  value={newWorkingModelId}
                  onChange={(e) => setNewWorkingModelId(String(e.target.value))}
                >
                  <MenuItem value="">Clear working model</MenuItem>
                  {workingModels.map((w) => (
                    <MenuItem key={w.id} value={w.id}>
                      {w.name}
                    </MenuItem>
                  ))}
                </FilterSelect>
              </Grid>
            ) : null}
            <Grid size={{ xs: 12, md: 12 }}>
              <Button
                variant="contained"
                disabled={disabled}
                startIcon={
                  action === 'transfer' ? (
                    <SwapHorizRoundedIcon />
                  ) : action === 'promote' ? (
                    <WorkspacePremiumRoundedIcon />
                  ) : (
                    <PaidRoundedIcon />
                  )
                }
                onClick={() => mutation.mutate()}
              >
                Record change
              </Button>
            </Grid>
          </>
        ) : null}
      </Grid>

      {employeeId ? (
        historyQuery.isLoading ? (
          <LoadingState message="Loading history…" />
        ) : (
          <Box sx={{ borderRadius: 2, p: 1.75, border: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              Change history
            </Typography>
            {(historyQuery.data?.events.length ?? 0) === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No recorded lifecycle changes.
              </Typography>
            ) : (
              <Stack spacing={0.75}>
                {historyQuery.data?.events.map((ev) => (
                  <Stack
                    key={ev.id}
                    direction="row"
                    spacing={1}
                    sx={{ alignItems: 'center', flexWrap: 'wrap' }}
                  >
                    <Chip size="small" label={EVENT_LABEL[ev.event_type] ?? ev.event_type} />
                    <Typography variant="body2">effective {ev.effective_date}</Typography>
                    <Typography variant="caption" color={ev.applied_at ? 'success.main' : 'warning.main'}>
                      {ev.applied_at ? 'applied' : 'pending'}
                    </Typography>
                    {ev.created_by_name ? (
                      <Typography variant="caption" color="text.secondary">
                        by {ev.created_by_name}
                      </Typography>
                    ) : null}
                  </Stack>
                ))}
              </Stack>
            )}

            {(historyQuery.data?.working_model_periods.length ?? 0) > 0 ? (
              <>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mt: 1.5, mb: 1 }}>
                  Billing / working-model periods
                </Typography>
                <Stack spacing={0.5}>
                  {historyQuery.data?.working_model_periods.map((p) => (
                    <Typography key={p.id} variant="body2">
                      {p.working_model_name ?? 'None'} · {p.effective_from} →{' '}
                      {p.effective_to ?? 'present'}
                    </Typography>
                  ))}
                </Stack>
              </>
            ) : null}
          </Box>
        )
      ) : null}
    </Stack>
  );
}

export default UserLifecyclePanel;
