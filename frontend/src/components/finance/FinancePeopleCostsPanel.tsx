import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  Checkbox,
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
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { teamQueryParam } from './FinanceTeamFilter';

type RosterItem = {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  team_names: string[];
  requires_salary: boolean;
  has_profile: boolean;
  monthly_salary: number | null;
  hourly_cost: number | null;
  currency_code: string | null;
  effective_from: string | null;
};

type Draft = {
  monthly_salary: string;
  hourly_cost: string;
  currency_code: string;
  effective_from: string;
};

function rosterQueryString(teamId: string, includeExempt: boolean): string {
  const base = teamQueryParam(teamId);
  if (!includeExempt) return base;
  if (!base) return '?include_exempt=true';
  return `${base}&include_exempt=true`;
}

export function FinancePeopleCostsPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [missingOnly, setMissingOnly] = useState(false);
  const [showExempt, setShowExempt] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const q = rosterQueryString(teamId, showExempt);

  const rosterQuery = useQuery({
    queryKey: ['finance-employee-roster', teamId || 'all', showExempt ? 'with-exempt' : 'required'],
    queryFn: async () =>
      (await apiClient.get<RosterItem[]>(`/finance/employee-costs/roster${q}`)).data,
  });

  const saveMutation = useMutation({
    mutationFn: async (payload: { userId: string; draft: Draft }) =>
      (
        await apiClient.post('/finance/employee-costs', {
          user_id: payload.userId,
          monthly_salary: payload.draft.monthly_salary || '0',
          hourly_cost: payload.draft.hourly_cost || '0',
          currency_code: payload.draft.currency_code || 'INR',
          effective_from: payload.draft.effective_from,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Salary saved');
      void queryClient.invalidateQueries({ queryKey: ['finance-employee-roster'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: { response?: { data?: { detail?: string } }; message?: string }) => {
      showError(error.response?.data?.detail ?? error.message ?? 'Could not save salary');
    },
  });

  const rows = useMemo(() => {
    const list = rosterQuery.data ?? [];
    return missingOnly
      ? list.filter((row) => row.requires_salary !== false && !row.has_profile)
      : list;
  }, [rosterQuery.data, missingOnly]);

  const ensureDraft = (row: RosterItem): Draft => {
    if (drafts[row.user_id]) return drafts[row.user_id];
    return {
      monthly_salary: row.monthly_salary != null ? String(row.monthly_salary) : '',
      hourly_cost: row.hourly_cost != null ? String(row.hourly_cost) : '',
      currency_code: row.currency_code ?? 'INR',
      effective_from: row.effective_from ?? new Date().toISOString().slice(0, 10),
    };
  };

  const setDraftField = (userId: string, field: keyof Draft, value: string, row: RosterItem) => {
    const base = ensureDraft(row);
    setDrafts((prev) => ({ ...prev, [userId]: { ...base, [field]: value } }));
  };

  return (
    <Stack spacing={2}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Typography variant="body2" color="text.secondary">
          {teamId
            ? 'Employees for the selected team (primary membership preferred). Salary-exempt accounts are hidden unless shown.'
            : 'Active employees who require salary. Use Show salary-exempt for Admin / Planning Board accounts.'}
        </Typography>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
          <FormControlLabel
            control={
              <Checkbox checked={showExempt} onChange={(e) => setShowExempt(e.target.checked)} />
            }
            label="Show salary-exempt"
          />
          <FormControlLabel
            control={<Checkbox checked={missingOnly} onChange={(e) => setMissingOnly(e.target.checked)} />}
            label="Missing salary only"
          />
        </Stack>
      </Box>

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Employee</TableCell>
            <TableCell>Team(s)</TableCell>
            <TableCell>Monthly salary</TableCell>
            <TableCell>Hourly cost</TableCell>
            <TableCell>Currency</TableCell>
            <TableCell>Effective</TableCell>
            <TableCell align="right">Action</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => {
            const draft = ensureDraft(row);
            const exempt = row.requires_salary === false;
            return (
              <TableRow key={row.user_id} hover>
                <TableCell>
                  <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {row.first_name} {row.last_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.email}
                        {!row.has_profile && !exempt ? ' · missing profile' : ''}
                      </Typography>
                    </Box>
                    {exempt ? <Chip size="small" label="Salary not required" variant="outlined" /> : null}
                  </Stack>
                </TableCell>
                <TableCell>{row.team_names.join(', ') || '—'}</TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    value={draft.monthly_salary}
                    onChange={(e) => setDraftField(row.user_id, 'monthly_salary', e.target.value, row)}
                    disabled={exempt}
                    sx={{ width: 110 }}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    value={draft.hourly_cost}
                    onChange={(e) => setDraftField(row.user_id, 'hourly_cost', e.target.value, row)}
                    disabled={exempt}
                    sx={{ width: 100 }}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    value={draft.currency_code}
                    onChange={(e) => setDraftField(row.user_id, 'currency_code', e.target.value, row)}
                    disabled={exempt}
                    sx={{ width: 80 }}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    type="date"
                    value={draft.effective_from}
                    onChange={(e) => setDraftField(row.user_id, 'effective_from', e.target.value, row)}
                    disabled={exempt}
                    slotProps={{ inputLabel: { shrink: true } }}
                    sx={{ width: 150 }}
                  />
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    variant="contained"
                    disabled={exempt || saveMutation.isPending}
                    onClick={() => {
                      const next = ensureDraft(row);
                      setDrafts((prev) => ({ ...prev, [row.user_id]: next }));
                      saveMutation.mutate({ userId: row.user_id, draft: next });
                    }}
                  >
                    Save
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No employees match this filter.
        </Typography>
      ) : null}
    </Stack>
  );
}
