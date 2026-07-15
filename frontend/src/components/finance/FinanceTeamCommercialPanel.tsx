import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { fetchTeams, fetchWorkingModels } from '../../api/lookups';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useToast } from '../../context/ToastContext';
import { teamQueryParam } from './FinanceTeamFilter';
import { apiErrorMessage } from '../../utils/apiErrorMessage';

type WorkingModel = {
  id: string;
  name: string;
  strategy_key?: string;
  code?: string;
};

type TeamCommercial = {
  id: string;
  team_id: string;
  team_name?: string | null;
  working_model_id: string;
  working_model_name?: string | null;
  working_model_strategy?: string | null;
  billing_mode: string;
  customer_fee_amount: number;
  currency_code: string;
  billing_period: string;
  effective_from: string;
  notes?: string | null;
  customer_pays_software?: boolean;
  customer_pays_hardware?: boolean;
  resource_count?: number | null;
  monthly_fee_signal_inr?: number | null;
};

function isRetainer(strategy?: string | null) {
  return strategy === 'retainer';
}

function showsCustomerFee(strategy?: string | null) {
  return isRetainer(strategy);
}

export function FinanceTeamCommercialPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TeamCommercial | null>(null);
  const [form, setForm] = useState({
    team_id: teamId,
    working_model_id: '',
    customer_fee_amount: '',
    currency_code: 'INR',
    billing_period: 'monthly',
    effective_from: new Date().toISOString().slice(0, 10),
    notes: '',
    customer_pays_software: false,
    customer_pays_hardware: false,
  });

  useEffect(() => {
    if (!editingId && teamId) setForm((prev) => ({ ...prev, team_id: teamId }));
  }, [teamId, editingId]);

  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const modelsQuery = useQuery({
    queryKey: ['lookup-working-models'],
    queryFn: fetchWorkingModels,
  });
  const currenciesQuery = useQuery({
    queryKey: ['finance-currencies'],
    queryFn: async () =>
      (await apiClient.get<Array<{ code: string; name: string }>>('/finance/currencies')).data,
  });
  const q = teamQueryParam(teamId);
  const termsQuery = useQuery({
    queryKey: ['finance-team-commercial', teamId || 'all'],
    queryFn: async () =>
      (await apiClient.get<TeamCommercial[]>(`/finance/team-commercial${q}`)).data,
  });

  const models = (modelsQuery.data ?? []) as WorkingModel[];
  const selectedModel = useMemo(
    () => models.find((m) => m.id === form.working_model_id),
    [models, form.working_model_id],
  );
  const strategy = selectedModel?.strategy_key ?? '';
  const needsFee = showsCustomerFee(strategy);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        team_id: form.team_id,
        working_model_id: form.working_model_id,
        customer_fee_amount: needsFee ? form.customer_fee_amount || '0' : '0',
        currency_code: form.currency_code,
        billing_period: form.billing_period,
        effective_from: form.effective_from,
        notes: form.notes || null,
        customer_pays_software: form.customer_pays_software,
        customer_pays_hardware: form.customer_pays_hardware,
      };
      if (editingId) {
        return (await apiClient.put(`/finance/team-commercial/${editingId}`, body)).data;
      }
      return (await apiClient.post('/finance/team-commercial', body)).data;
    },
    onSuccess: () => {
      showSuccess(editingId ? 'Team commercial terms updated' : 'Team commercial terms saved');
      setEditingId(null);
      setForm((prev) => ({
        ...prev,
        customer_fee_amount: '',
        notes: '',
        team_id: teamId || prev.team_id,
      }));
      void queryClient.invalidateQueries({ queryKey: ['finance-team-commercial'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save team commercial terms'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/finance/team-commercial/${id}`);
    },
    onSuccess: () => {
      showSuccess('Team commercial terms deleted');
      setDeleteTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['finance-team-commercial'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not delete terms'));
    },
  });

  const startEdit = (row: TeamCommercial) => {
    setEditingId(row.id);
    setForm({
      team_id: row.team_id,
      working_model_id: row.working_model_id,
      customer_fee_amount: String(row.customer_fee_amount ?? ''),
      currency_code: row.currency_code || 'INR',
      billing_period: row.billing_period || 'monthly',
      effective_from: row.effective_from,
      notes: row.notes || '',
      customer_pays_software: Boolean(row.customer_pays_software),
      customer_pays_hardware: Boolean(row.customer_pays_hardware),
    });
  };

  const teams = teamsQuery.data ?? [];
  const canSave =
    Boolean(form.team_id && form.working_model_id) &&
    (!needsFee || Boolean(form.customer_fee_amount)) &&
    !saveMutation.isPending;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {editingId ? 'Edit team commercial terms' : 'Team cost / commercial model'}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Working model drives commercial rules. Retainer uses rate per resource / month × salary-required
          headcount. Project-based / T&amp;M planning revenue comes from quotes — no team flat fee.
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Team</InputLabel>
            <Select
              label="Team"
              value={form.team_id}
              onChange={(e) => setForm((p) => ({ ...p, team_id: e.target.value }))}
            >
              {teams.map((team) => (
                <MenuItem key={team.id} value={team.id}>
                  {team.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Working model</InputLabel>
            <Select
              label="Working model"
              value={form.working_model_id}
              onChange={(e) => {
                const nextId = e.target.value;
                const next = models.find((m) => m.id === nextId);
                setForm((p) => ({
                  ...p,
                  working_model_id: nextId,
                  billing_period:
                    next?.strategy_key === 'project_based' ? 'one_time' : p.billing_period || 'monthly',
                  customer_fee_amount:
                    next?.strategy_key === 'retainer' ? p.customer_fee_amount : '',
                }));
              }}
            >
              {models.map((model) => (
                <MenuItem key={model.id} value={model.id}>
                  {model.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {needsFee ? (
            <TextField
              size="small"
              label="Rate per resource / month"
              value={form.customer_fee_amount}
              onChange={(e) => setForm((p) => ({ ...p, customer_fee_amount: e.target.value }))}
              helperText="Overview fee = rate × billable salary-required headcount (excludes management overhead)"
            />
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ alignSelf: 'center', maxWidth: 280 }}>
              No team customer fee for this model — use Revenue / quotes for project revenue.
            </Typography>
          )}
          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>Currency</InputLabel>
            <Select
              label="Currency"
              value={form.currency_code}
              onChange={(e) => setForm((p) => ({ ...p, currency_code: e.target.value }))}
            >
              {(currenciesQuery.data ?? [{ code: 'INR' }, { code: 'USD' }, { code: 'EUR' }]).map(
                (c) => (
                  <MenuItem key={c.code} value={c.code}>
                    {c.code}
                  </MenuItem>
                ),
              )}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>Period</InputLabel>
            <Select
              label="Period"
              value={form.billing_period}
              onChange={(e) => setForm((p) => ({ ...p, billing_period: e.target.value }))}
            >
              <MenuItem value="monthly">Monthly</MenuItem>
              <MenuItem value="quarterly">Quarterly</MenuItem>
              <MenuItem value="annual">Annual</MenuItem>
              <MenuItem value="one_time">One-time</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            type="date"
            label="Effective from"
            value={form.effective_from}
            onChange={(e) => setForm((p) => ({ ...p, effective_from: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={form.customer_pays_software}
                onChange={(e) => setForm((p) => ({ ...p, customer_pays_software: e.target.checked }))}
              />
            }
            label="Customer pays software"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={form.customer_pays_hardware}
                onChange={(e) => setForm((p) => ({ ...p, customer_pays_hardware: e.target.checked }))}
              />
            }
            label="Customer pays hardware"
          />
          <Button variant="contained" disabled={!canSave} onClick={() => saveMutation.mutate()}>
            {editingId ? 'Save changes' : 'Save terms'}
          </Button>
          {editingId ? (
            <Button
              variant="outlined"
              onClick={() => {
                setEditingId(null);
                setForm((prev) => ({
                  ...prev,
                  customer_fee_amount: '',
                  notes: '',
                  team_id: teamId || prev.team_id,
                }));
              }}
            >
              Cancel
            </Button>
          ) : null}
        </Stack>
      </Box>

      <Stack spacing={1}>
        {(termsQuery.data ?? []).map((row) => (
          <Card key={row.id} variant="outlined">
            <CardContent
              sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}
            >
              <Box>
                <Typography sx={{ fontWeight: 600 }}>
                  {row.team_name ?? row.team_id} · {row.working_model_name ?? 'Model'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {isRetainer(row.working_model_strategy)
                    ? `Rate ${row.customer_fee_amount} ${row.currency_code}/resource/mo × ${row.resource_count ?? 0} billable ≈ ${row.monthly_fee_signal_inr ?? 0} INR/mo`
                    : `No team flat fee (quotes drive revenue) · ${row.billing_period}`}
                  {` · from ${row.effective_from}`}
                  {row.customer_pays_software ? ' · customer SW' : ''}
                  {row.customer_pays_hardware ? ' · customer HW' : ''}
                </Typography>
                {isRetainer(row.working_model_strategy) ? (
                  <Typography variant="caption" color="text.secondary">
                    Billable resources exclude management / overhead (Billable headcount off).
                  </Typography>
                ) : null}
              </Box>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Button size="small" variant="contained" onClick={() => startEdit(row)}>
                  Edit
                </Button>
                <Button size="small" color="error" variant="outlined" onClick={() => setDeleteTarget(row)}>
                  Delete
                </Button>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete team commercial terms?"
        message="This deactivates the terms so they no longer appear in Overview fee signals."
        recordName={
          deleteTarget
            ? `${deleteTarget.team_name ?? deleteTarget.team_id} · ${deleteTarget.working_model_name ?? 'Model'}`
            : undefined
        }
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
      />
    </Stack>
  );
}
