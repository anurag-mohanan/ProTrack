import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  Checkbox,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import PaymentsOutlinedIcon from '@mui/icons-material/PaymentsOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { apiErrorMessage } from '../../utils/apiErrorMessage';
import { toFiniteNumber } from '../../utils/format';
import { LoadingState } from '../common/LoadingState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { teamQueryParam } from './FinanceTeamFilter';
import {
  FinanceHeroBanner,
  FinanceSection,
  financeMoney,
} from './FinanceCockpitPrimitives';

type RosterItem = {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  team_names: string[];
  requires_salary: boolean;
  has_profile: boolean;
  monthly_salary: number | null;
  currency_code: string | null;
  effective_from: string | null;
  leaving_date?: string | null;
  salary_month_factor?: string | null;
};

type Draft = {
  monthly_salary: string;
  currency_code: string;
  effective_from: string;
  leaving_date: string;
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
    mutationFn: async (payload: { userId: string; draft: Draft }) => {
      await apiClient.patch(`/finance/employee-costs/roster/${payload.userId}/leaving-date`, {
        leaving_date: payload.draft.leaving_date || null,
      });
      return (
        await apiClient.post('/finance/employee-costs', {
          user_id: payload.userId,
          monthly_salary: payload.draft.monthly_salary || '0',
          hourly_cost: '0',
          currency_code: payload.draft.currency_code || 'INR',
          effective_from: payload.draft.effective_from,
        })
      ).data;
    },
    onSuccess: () => {
      showSuccess('Salary / last working day saved');
      void queryClient.invalidateQueries({ queryKey: ['finance-employee-roster'] });
      void queryClient.invalidateQueries({ queryKey: ['finance-dashboard'] });
    },
    onError: (error: unknown) => {
      showError(apiErrorMessage(error, 'Could not save salary'));
    },
  });

  const allRows = rosterQuery.data ?? [];
  const rows = useMemo(() => {
    return missingOnly
      ? allRows.filter((row) => row.requires_salary !== false && !row.has_profile)
      : allRows;
  }, [allRows, missingOnly]);

  const stats = useMemo(() => {
    const required = allRows.filter((r) => r.requires_salary !== false);
    const missing = required.filter((r) => !r.has_profile).length;
    const exempt = allRows.filter((r) => r.requires_salary === false).length;
    const salarySum = required.reduce((sum, r) => {
      const factor = toFiniteNumber(r.salary_month_factor ?? 1);
      return sum + toFiniteNumber(r.monthly_salary) * factor;
    }, 0);
    return {
      headcount: required.length,
      missing,
      exempt,
      salarySum,
    };
  }, [allRows]);

  const ensureDraft = (row: RosterItem): Draft => {
    if (drafts[row.user_id]) return drafts[row.user_id];
    return {
      monthly_salary: row.monthly_salary != null ? String(row.monthly_salary) : '',
      currency_code: row.currency_code ?? 'INR',
      effective_from: row.effective_from ?? new Date().toISOString().slice(0, 10),
      leaving_date: row.leaving_date ?? '',
    };
  };

  const setDraftField = (userId: string, field: keyof Draft, value: string, row: RosterItem) => {
    const base = ensureDraft(row);
    setDrafts((prev) => ({ ...prev, [userId]: { ...base, [field]: value } }));
  };

  if (rosterQuery.isLoading) {
    return <LoadingState message="Loading people costs…" />;
  }

  return (
    <Stack spacing={2.5}>
      <FinanceHeroBanner
        title="People costs"
        subtitle="Salary roster with last working day proration — costs stop after the leave date so Annual Plan wages and overhead CPR stay realistic."
        chips={
          <>
            <Chip size="small" label={teamId ? 'Team scope' : 'All teams'} sx={{ fontWeight: 700 }} />
            {stats.missing > 0 ? (
              <Chip size="small" color="warning" label={`${stats.missing} missing salary`} />
            ) : (
              <Chip size="small" color="success" label="Salaries complete" />
            )}
          </>
        }
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={GroupsOutlinedIcon}
            title="Salary headcount"
            value={String(stats.headcount)}
            subtitle="Requires salary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="warning"
            icon={WarningAmberOutlinedIcon}
            title="Missing profiles"
            value={String(stats.missing)}
            subtitle="Need salary entry"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={PaymentsOutlinedIcon}
            title="Salary Σ / mo"
            value={financeMoney(stats.salarySum, 'INR')}
            subtitle="Prorated this month"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="success"
            icon={BadgeOutlinedIcon}
            title="Salary-exempt"
            value={String(stats.exempt)}
            subtitle={showExempt ? 'Shown in roster' : 'Hidden unless toggled'}
          />
        </Grid>
      </Grid>

      <FinanceSection
        title="Salary roster"
        subtitle={
          teamId
            ? 'Employees for the selected team. Set Last working day so salaries stop after that date.'
            : 'Set Last working day when someone leaves — monthly salary prorates in that month and drops after.'
        }
        action={
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <FormControlLabel
              control={
                <Checkbox checked={showExempt} onChange={(e) => setShowExempt(e.target.checked)} />
              }
              label="Show salary-exempt"
            />
            <FormControlLabel
              control={
                <Checkbox checked={missingOnly} onChange={(e) => setMissingOnly(e.target.checked)} />
              }
              label="Missing salary only"
            />
          </Stack>
        }
      >
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Employee</TableCell>
                <TableCell>Team(s)</TableCell>
                <TableCell>Monthly salary</TableCell>
                <TableCell>Currency</TableCell>
                <TableCell>Effective</TableCell>
                <TableCell>Last working day</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary">
                      No employees match the current filters.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((row) => {
                  const draft = ensureDraft(row);
                  const exempt = row.requires_salary === false;
                  const factor = Number(row.salary_month_factor ?? 1);
                  return (
                    <TableRow key={row.user_id} hover>
                      <TableCell>
                        <Stack
                          direction="row"
                          spacing={1}
                          useFlexGap
                          sx={{ flexWrap: 'wrap', alignItems: 'center' }}
                        >
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {row.first_name} {row.last_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {row.email}
                              {!row.has_profile && !exempt ? ' · missing profile' : ''}
                            </Typography>
                          </Box>
                          {exempt ? (
                            <Chip size="small" label="Salary not required" variant="outlined" />
                          ) : null}
                          {factor > 0 && factor < 1 ? (
                            <Chip
                              size="small"
                              color="warning"
                              label={`${Math.round(factor * 100)}% this month`}
                            />
                          ) : null}
                          {factor === 0 ? (
                            <Chip size="small" color="default" label="Left" />
                          ) : null}
                        </Stack>
                      </TableCell>
                      <TableCell>{row.team_names.join(', ') || '—'}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={draft.monthly_salary}
                          onChange={(e) =>
                            setDraftField(row.user_id, 'monthly_salary', e.target.value, row)
                          }
                          disabled={exempt}
                          sx={{ width: 110 }}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={draft.currency_code}
                          onChange={(e) =>
                            setDraftField(row.user_id, 'currency_code', e.target.value, row)
                          }
                          disabled={exempt}
                          sx={{ width: 80 }}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          type="date"
                          value={draft.effective_from}
                          onChange={(e) =>
                            setDraftField(row.user_id, 'effective_from', e.target.value, row)
                          }
                          disabled={exempt}
                          slotProps={{ inputLabel: { shrink: true } }}
                          sx={{ width: 150 }}
                        />
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          type="date"
                          value={draft.leaving_date}
                          onChange={(e) =>
                            setDraftField(row.user_id, 'leaving_date', e.target.value, row)
                          }
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
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </FinanceSection>
    </Stack>
  );
}
