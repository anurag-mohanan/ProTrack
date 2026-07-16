import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  FormControlLabel,
  Checkbox,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
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
  is_active: boolean;
  team_names: string[];
  requires_salary: boolean;
  has_profile: boolean;
  monthly_salary: number | null;
  base_monthly_salary_inr?: number | null;
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

type StatusFilter = 'active' | 'leaving' | 'inactive' | 'all';
type SortField =
  | 'name'
  | 'team'
  | 'salary'
  | 'factor'
  | 'effective'
  | 'leaving';

function rosterQueryString(
  teamId: string,
  includeExempt: boolean,
  includeInactive: boolean,
): string {
  const base = teamQueryParam(teamId);
  const params = new URLSearchParams(base.startsWith('?') ? base.slice(1) : '');
  if (includeExempt) params.set('include_exempt', 'true');
  if (includeInactive) params.set('include_inactive', 'true');
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function FinancePeopleCostsPanel({ teamId }: { teamId: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [missingOnly, setMissingOnly] = useState(false);
  const [showExempt, setShowExempt] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const q = rosterQueryString(teamId, showExempt, showInactive);

  const rosterQuery = useQuery({
    queryKey: [
      'finance-employee-roster',
      teamId || 'all',
      showExempt ? 'with-exempt' : 'required',
      showInactive ? 'with-inactive' : 'active-only',
    ],
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
  const todayIso = new Date().toISOString().slice(0, 10);
  const currentMonth = todayIso.slice(0, 7);
  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    const filtered = allRows.filter((row) => {
      if (missingOnly && (row.requires_salary === false || row.has_profile)) return false;
      if (term) {
        const haystack = [
          row.first_name,
          row.last_name,
          row.email,
          row.team_names.join(' '),
        ]
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(term)) return false;
      }
      const leavingMonth = row.leaving_date?.slice(0, 7);
      const isLeavingThisMonth = Boolean(leavingMonth && leavingMonth === currentMonth);
      if (statusFilter === 'active' && !row.is_active) return false;
      if (statusFilter === 'leaving' && !isLeavingThisMonth) return false;
      if (statusFilter === 'inactive' && row.is_active) return false;
      return true;
    });

    const sorted = [...filtered];
    sorted.sort((left, right) => {
      const direction = sortDirection === 'asc' ? 1 : -1;
      const nameLeft = `${left.first_name} ${left.last_name}`.trim();
      const nameRight = `${right.first_name} ${right.last_name}`.trim();
      const pick = (row: RosterItem) => {
        switch (sortField) {
          case 'team':
            return row.team_names.join(', ');
          case 'salary':
            return toFiniteNumber(row.base_monthly_salary_inr ?? row.monthly_salary);
          case 'factor':
            return toFiniteNumber(row.salary_month_factor ?? 0);
          case 'effective':
            return row.effective_from ?? '';
          case 'leaving':
            return row.leaving_date ?? '';
          case 'name':
          default:
            return nameLeft;
        }
      };
      if (sortField === 'name') {
        return nameLeft.localeCompare(nameRight) * direction;
      }
      if (sortField === 'team') {
        return left.team_names.join(', ').localeCompare(right.team_names.join(', ')) * direction;
      }
      if (sortField === 'effective' || sortField === 'leaving') {
        const a = (sortField === 'effective' ? left.effective_from : left.leaving_date) ?? '';
        const b = (sortField === 'effective' ? right.effective_from : right.leaving_date) ?? '';
        return a.localeCompare(b) * direction;
      }
      return (
        (Number(pick(left)) - Number(
          sortField === 'salary'
            ? toFiniteNumber(right.base_monthly_salary_inr ?? right.monthly_salary)
            : toFiniteNumber(right.salary_month_factor ?? 0),
        )) * direction
      );
    });
    return sorted;
  }, [allRows, currentMonth, missingOnly, search, sortDirection, sortField, statusFilter]);

  const stats = useMemo(() => {
    const required = allRows.filter((r) => r.requires_salary !== false);
    const missing = required.filter((r) => !r.has_profile).length;
    const exempt = allRows.filter((r) => r.requires_salary === false).length;
    const inactive = allRows.filter((r) => !r.is_active).length;
    const leavingThisMonth = allRows.filter((r) => r.leaving_date?.slice(0, 7) === currentMonth).length;
    const salarySum = required.reduce((sum, r) => {
      const factor = toFiniteNumber(r.salary_month_factor ?? 1);
      return sum + toFiniteNumber(r.monthly_salary) * factor;
    }, 0);
    const complete = required.length > 0 ? ((required.length - missing) / required.length) * 100 : 100;
    const highestSalary = required.reduce(
      (max, r) => Math.max(max, toFiniteNumber(r.base_monthly_salary_inr ?? r.monthly_salary)),
      0,
    );
    return {
      headcount: required.length,
      missing,
      exempt,
      inactive,
      leavingThisMonth,
      salarySum,
      complete,
      highestSalary,
    };
  }, [allRows, currentMonth]);

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

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortField(field);
    setSortDirection(field === 'name' || field === 'team' ? 'asc' : 'desc');
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
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent={stats.leavingThisMonth > 0 ? 'warning' : 'success'}
            icon={WarningAmberOutlinedIcon}
            title="Leaving this month"
            value={String(stats.leavingThisMonth)}
            subtitle="Needs handover / proration check"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={BadgeOutlinedIcon}
            title="Profile completeness"
            value={`${stats.complete.toFixed(0)}%`}
            subtitle={`${stats.headcount - stats.missing}/${stats.headcount} covered`}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="primary"
            icon={PaymentsOutlinedIcon}
            title="Highest salary"
            value={financeMoney(stats.highestSalary, 'INR')}
            subtitle="Largest active monthly salary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            compact
            accent="info"
            icon={GroupsOutlinedIcon}
            title="Inactive shown"
            value={String(stats.inactive)}
            subtitle={showInactive ? 'Historical roster rows included' : 'Hidden unless toggled'}
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
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
            <TextField
              size="small"
              placeholder="Search employee or team"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{ minWidth: 220 }}
            />
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Status</InputLabel>
              <Select
                label="Status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              >
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="leaving">Leaving this month</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
                <MenuItem value="all">All shown</MenuItem>
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Checkbox checked={showExempt} onChange={(e) => setShowExempt(e.target.checked)} />
              }
              label="Show salary-exempt"
            />
            <FormControlLabel
              control={
                <Checkbox checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
              }
              label="Show inactive history"
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
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'name'}
                    direction={sortField === 'name' ? sortDirection : 'asc'}
                    onClick={() => toggleSort('name')}
                  >
                    Employee
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'team'}
                    direction={sortField === 'team' ? sortDirection : 'asc'}
                    onClick={() => toggleSort('team')}
                  >
                    Team(s)
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'salary'}
                    direction={sortField === 'salary' ? sortDirection : 'desc'}
                    onClick={() => toggleSort('salary')}
                  >
                    Monthly salary
                  </TableSortLabel>
                </TableCell>
                <TableCell>Currency</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'effective'}
                    direction={sortField === 'effective' ? sortDirection : 'desc'}
                    onClick={() => toggleSort('effective')}
                  >
                    Effective
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={sortField === 'leaving'}
                    direction={sortField === 'leaving' ? sortDirection : 'desc'}
                    onClick={() => toggleSort('leaving')}
                  >
                    Last working day
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortField === 'factor'}
                    direction={sortField === 'factor' ? sortDirection : 'desc'}
                    onClick={() => toggleSort('factor')}
                  >
                    Month factor
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8}>
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
                          {!row.is_active ? (
                            <Chip size="small" color="default" label="Inactive" />
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
                        <Stack spacing={0.75}>
                          <TextField
                            size="small"
                            value={draft.monthly_salary}
                            onChange={(e) =>
                              setDraftField(row.user_id, 'monthly_salary', e.target.value, row)
                            }
                            disabled={exempt}
                            sx={{ width: 110 }}
                          />
                          {row.base_monthly_salary_inr != null ? (
                            <Typography variant="caption" color="text.secondary">
                              {financeMoney(row.base_monthly_salary_inr, 'INR')}
                            </Typography>
                          ) : null}
                        </Stack>
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
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {Math.round(factor * 100)}%
                        </Typography>
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
