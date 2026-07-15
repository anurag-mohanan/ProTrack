import { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
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
import { useToast } from '../../context/ToastContext';

type TeamCommercial = {
  id: string;
  team_id: string;
  team_name?: string | null;
  working_model_id: string;
  working_model_name?: string | null;
  billing_mode: string;
  customer_fee_amount: number;
  currency_code: string;
  billing_period: string;
  effective_from: string;
  notes?: string | null;
};

export function FinanceTeamCommercialPanel() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    team_id: '',
    working_model_id: '',
    billing_mode: 'subscription',
    customer_fee_amount: '',
    currency_code: 'INR',
    billing_period: 'monthly',
    effective_from: new Date().toISOString().slice(0, 10),
    notes: '',
  });

  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const modelsQuery = useQuery({
    queryKey: ['lookup-working-models'],
    queryFn: fetchWorkingModels,
  });
  const termsQuery = useQuery({
    queryKey: ['finance-team-commercial'],
    queryFn: async () => (await apiClient.get<TeamCommercial[]>('/finance/team-commercial')).data,
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post('/finance/team-commercial', {
          team_id: form.team_id,
          working_model_id: form.working_model_id,
          billing_mode: form.billing_mode,
          customer_fee_amount: form.customer_fee_amount,
          currency_code: form.currency_code,
          billing_period: form.billing_period,
          effective_from: form.effective_from,
          notes: form.notes || null,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Team commercial terms saved');
      setForm((prev) => ({ ...prev, customer_fee_amount: '', notes: '' }));
      void queryClient.invalidateQueries({ queryKey: ['finance-team-commercial'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      showError(error.response?.data?.detail ?? 'Could not save team commercial terms');
    },
  });

  const teams = (teamsQuery.data ?? []) as Array<{ id: string; name: string }>;
  const models = (modelsQuery.data ?? []) as Array<{ id: string; name: string }>;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Team cost / commercial model
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Select the engagement model and the fixed / subscription fee the customer pays so finance
          calculations stay accurate.
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
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Working model</InputLabel>
            <Select
              label="Working model"
              value={form.working_model_id}
              onChange={(e) => setForm((p) => ({ ...p, working_model_id: e.target.value }))}
            >
              {models.map((model) => (
                <MenuItem key={model.id} value={model.id}>
                  {model.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Billing mode</InputLabel>
            <Select
              label="Billing mode"
              value={form.billing_mode}
              onChange={(e) => setForm((p) => ({ ...p, billing_mode: e.target.value }))}
            >
              <MenuItem value="fixed_price">Fixed price</MenuItem>
              <MenuItem value="subscription">Subscription</MenuItem>
              <MenuItem value="time_materials">Time &amp; materials</MenuItem>
              <MenuItem value="project_based">Project based</MenuItem>
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Customer fee"
            value={form.customer_fee_amount}
            onChange={(e) => setForm((p) => ({ ...p, customer_fee_amount: e.target.value }))}
          />
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
            InputLabelProps={{ shrink: true }}
          />
          <Button
            variant="contained"
            disabled={
              !form.team_id ||
              !form.working_model_id ||
              !form.customer_fee_amount ||
              createMutation.isPending
            }
            onClick={() => createMutation.mutate()}
          >
            Save terms
          </Button>
        </Stack>
      </Box>

      <Stack spacing={1}>
        {(termsQuery.data ?? []).map((row) => (
          <Card key={row.id} variant="outlined">
            <CardContent>
              <Typography sx={{ fontWeight: 600 }}>
                {row.team_name ?? row.team_id} · {row.working_model_name ?? 'Model'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {row.billing_mode} · {row.customer_fee_amount} {row.currency_code} / {row.billing_period}{' '}
                · from {row.effective_from}
              </Typography>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}
