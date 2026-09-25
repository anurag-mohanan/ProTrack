import { useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  LinearProgress,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import PersonAddAltRoundedIcon from '@mui/icons-material/PersonAddAltRounded';
import EventAvailableRoundedIcon from '@mui/icons-material/EventAvailableRounded';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import AssignmentLateRoundedIcon from '@mui/icons-material/AssignmentLateRounded';
import ChecklistRoundedIcon from '@mui/icons-material/ChecklistRounded';
import TaskAltRoundedIcon from '@mui/icons-material/TaskAltRounded';
import { apiClient } from '../api/client';
import {
  fetchHrDashboardOverview,
  fetchHrSegmentEmployees,
  hrDashboardKeys,
  type HrBreakdownRow,
  type HrDashboardFilters,
} from '../api/hrDashboard';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { ContentCard } from '../components/ui/cards';
import { FormSelect, KpiMetricCard } from '../components/ui/design-system';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { formatDate } from '../utils/format';

type Drilldown = { segment: string; title: string };

const PERIOD_OPTIONS = [
  { value: 'this_month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
  { value: 'this_quarter', label: 'This quarter' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'this_year', label: 'This year' },
];

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active employees' },
  { value: 'inactive', label: 'Inactive / exited' },
  { value: 'all', label: 'All employees' },
];

const SEVERITY_COLOR = { high: 'error', medium: 'warning', low: 'default' } as const;

function iso(d: Date): string {
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function periodRange(preset: string): { start_date: string; end_date: string } {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  switch (preset) {
    case 'last_month':
      return { start_date: iso(new Date(y, m - 1, 1)), end_date: iso(new Date(y, m, 0)) };
    case 'this_quarter': {
      const q = Math.floor(m / 3) * 3;
      return { start_date: iso(new Date(y, q, 1)), end_date: iso(new Date(y, q + 3, 0)) };
    }
    case 'last_90_days':
      return { start_date: iso(new Date(y, m, now.getDate() - 89)), end_date: iso(now) };
    case 'this_year':
      return { start_date: iso(new Date(y, 0, 1)), end_date: iso(new Date(y, 11, 31)) };
    default:
      return { start_date: iso(new Date(y, m, 1)), end_date: iso(new Date(y, m + 1, 0)) };
  }
}

function BreakdownList({
  rows,
  total,
  onSelect,
  emptyText,
}: {
  rows: HrBreakdownRow[];
  total: number;
  onSelect: (row: HrBreakdownRow) => void;
  emptyText: string;
}) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        {emptyText}
      </Typography>
    );
  }
  return (
    <Stack spacing={1}>
      {rows.slice(0, 12).map((row) => (
        <Box
          key={row.segment}
          onClick={() => onSelect(row)}
          sx={{ cursor: 'pointer', '&:hover .label': { textDecoration: 'underline' } }}
        >
          <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
            <Typography className="label" variant="body2">
              {row.label}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {row.count}
            </Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={total ? (100 * row.count) / total : 0}
            sx={{ height: 6, borderRadius: 3 }}
          />
        </Box>
      ))}
      {rows.length > 12 ? (
        <Typography variant="caption" color="text.secondary">
          +{rows.length - 12} more groups
        </Typography>
      ) : null}
    </Stack>
  );
}

function SegmentDialog({
  drilldown,
  filters,
  onClose,
}: {
  drilldown: Drilldown | null;
  filters: HrDashboardFilters;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: hrDashboardKeys.segment(drilldown?.segment ?? '', filters),
    queryFn: () => fetchHrSegmentEmployees(drilldown!.segment, filters),
    enabled: Boolean(drilldown),
  });
  const rows = query.data ?? [];
  return (
    <Dialog open={Boolean(drilldown)} onClose={onClose} fullWidth maxWidth="lg">
      <DialogTitle>
        {drilldown?.title}
        {query.data ? ` · ${rows.length}` : ''}
      </DialogTitle>
      <DialogContent>
        {query.isLoading ? (
          <LoadingState message="Loading employees…" />
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        ) : rows.length === 0 ? (
          <Typography color="text.secondary">No employees match.</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Employee</TableCell>
                <TableCell>Designation</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>Manager</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Shift today</TableCell>
                <TableCell>Joined</TableCell>
                <TableCell>Leaving</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.user_id}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {row.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.email}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.designation || '—'}</TableCell>
                  <TableCell>{row.department || '—'}</TableCell>
                  <TableCell>{row.manager || '—'}</TableCell>
                  <TableCell>{row.employment_type || '—'}</TableCell>
                  <TableCell>{row.shift || '—'}</TableCell>
                  <TableCell>{formatDate(row.joining_date) || '—'}</TableCell>
                  <TableCell>{formatDate(row.leaving_date) || '—'}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      color={row.status === 'active' ? 'success' : 'default'}
                      label={row.status === 'active' ? 'Active' : 'Inactive'}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={onClose}>
          Close
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

type TimesheetRow = {
  id: string;
  name: string;
  email: string;
  latest_timesheet_status: string;
  missing_days: number;
};

export function HrDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [drilldown, setDrilldown] = useState<Drilldown | null>(null);
  const period = searchParams.get('period') ?? 'this_month';

  const filters: HrDashboardFilters = useMemo(
    () => ({
      ...periodRange(period),
      org_department_id: searchParams.get('department') ?? undefined,
      designation: searchParams.get('designation') ?? undefined,
      manager_id: searchParams.get('manager') ?? undefined,
      shift_id: searchParams.get('shift') ?? undefined,
      employment_type: searchParams.get('employment_type') ?? undefined,
      status: (searchParams.get('status') as HrDashboardFilters['status']) ?? 'active',
    }),
    [period, searchParams],
  );

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const query = useQuery({
    queryKey: hrDashboardKeys.overview(filters),
    queryFn: () => fetchHrDashboardOverview(filters),
    placeholderData: keepPreviousData,
  });
  const timesheetQuery = useQuery({
    queryKey: ['hr-dashboard', 'timesheets'],
    queryFn: async () => (await apiClient.get('/hr/dashboard')).data,
  });

  if (query.isLoading) return <LoadingState message="Loading HR dashboard…" />;
  if (query.error || !query.data) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load HR dashboard"
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const cards = data.cards;
  const options = data.filter_options;
  const population = data.breakdowns.department.reduce((sum, row) => sum + row.count, 0);
  const open = (segment: string, title: string) => setDrilldown({ segment, title });
  const periodLabel = `${formatDate(data.period_start)} – ${formatDate(data.period_end)}`;
  const attention: TimesheetRow[] = timesheetQuery.data?.timesheet_attention ?? [];

  const withAll = (label: string, rows: { value: string; label: string }[]) => [
    { value: '', label },
    ...rows,
  ];

  const kpis = [
    { title: 'Total employees', value: cards.total_employees, segment: 'all', icon: GroupsRoundedIcon, accent: 'primary' as const },
    { title: 'Active', value: cards.active_employees, segment: 'active', icon: HowToRegRoundedIcon, accent: 'success' as const },
    { title: 'New joiners', value: cards.new_joiners, segment: 'joiners', icon: PersonAddAltRoundedIcon, accent: 'info' as const, subtitle: periodLabel },
    { title: `Upcoming joiners (${data.horizon_days}d)`, value: cards.upcoming_joiners, segment: 'upcoming_joiners', icon: EventAvailableRoundedIcon, accent: 'info' as const },
    { title: 'Exits', value: cards.exits, segment: 'exits', icon: LogoutRoundedIcon, accent: 'warning' as const, subtitle: periodLabel },
    { title: `Upcoming exits (${data.horizon_days}d)`, value: cards.upcoming_exits, segment: 'upcoming_exits', icon: ScheduleRoundedIcon, accent: 'warning' as const },
    { title: 'Onboarding in progress', value: cards.onboarding_in_progress, segment: 'onboarding_in_progress', icon: ChecklistRoundedIcon, accent: 'primary' as const },
    { title: 'Onboarding overdue', value: cards.onboarding_overdue, segment: 'onboarding_overdue', icon: AssignmentLateRoundedIcon, accent: cards.onboarding_overdue ? ('error' as const) : ('success' as const) },
  ];

  return (
    <PageContainer>
      <PageHeader
        title="HR Dashboard"
        subtitle={`Live from employee, onboarding, exit, shift and performance review records · as of ${formatDate(data.as_of)}. Click any figure to see the employees behind it.`}
      />

      <ContentCard>
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect label="Period" value={period} options={PERIOD_OPTIONS} onChange={(e) => setFilter('period', String(e.target.value))} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect label="Department" value={filters.org_department_id ?? ''} options={withAll('All departments', options.departments)} onChange={(e) => setFilter('department', String(e.target.value))} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect searchable label="Designation" value={filters.designation ?? ''} options={withAll('All designations', options.designations)} onChange={(e) => setFilter('designation', String(e.target.value))} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect searchable label="Manager" value={filters.manager_id ?? ''} options={withAll('All managers', options.managers)} onChange={(e) => setFilter('manager', String(e.target.value))} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect label="Shift (today)" value={filters.shift_id ?? ''} options={withAll('All shifts', options.shifts)} onChange={(e) => setFilter('shift', String(e.target.value))} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect label="Employment type" value={filters.employment_type ?? ''} options={withAll('All types', options.employment_types)} onChange={(e) => setFilter('employment_type', String(e.target.value))} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 12 / 7 }}>
            <FormSelect label="Status" value={filters.status ?? 'active'} options={STATUS_OPTIONS} onChange={(e) => setFilter('status', String(e.target.value))} />
          </Grid>
        </Grid>
      </ContentCard>

      <Stack spacing={2.5} sx={{ mt: 2.5 }}>
        <Grid container spacing={1.5}>
          {kpis.map((kpi) => (
            <Grid key={kpi.segment} size={{ xs: 12, sm: 6, md: 3 }}>
              <KpiMetricCard
                title={kpi.title}
                value={String(kpi.value)}
                icon={kpi.icon}
                accent={kpi.accent}
                subtitle={kpi.subtitle}
                onClick={() => open(kpi.segment, kpi.title)}
              />
            </Grid>
          ))}
        </Grid>

        <ContentCard
          title={`HR Action Center · ${cards.open_hr_actions}`}
          subtitle="Open items computed from records — click to see who is affected."
        >
          {data.actions.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No open HR actions for the current filters.
            </Typography>
          ) : (
            <Table size="small">
              <TableBody>
                {data.actions.map((action) => (
                  <TableRow key={action.code} hover sx={{ cursor: 'pointer' }} onClick={() => open(action.segment, action.title)}>
                    <TableCell sx={{ width: 90 }}>
                      <Chip size="small" color={SEVERITY_COLOR[action.severity]} label={action.severity} />
                    </TableCell>
                    <TableCell>{action.title}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {action.count}
                    </TableCell>
                    <TableCell align="right" sx={{ width: 140 }} onClick={(e) => e.stopPropagation()}>
                      {action.module_link ? (
                        <Link component={RouterLink} to={action.module_link}>
                          Open module
                        </Link>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>

        <ContentCard
          title="Headcount trend (12 months)"
          subtitle="Opening + joiners − exits = closing, from joining and leaving dates."
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Month</TableCell>
                <TableCell align="right">Opening</TableCell>
                <TableCell align="right">Joiners</TableCell>
                <TableCell align="right">Exits</TableCell>
                <TableCell align="right">Closing</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.trend.map((row) => (
                <TableRow key={row.month}>
                  <TableCell>{row.label}</TableCell>
                  <TableCell align="right">{row.opening}</TableCell>
                  <TableCell align="right">
                    {row.joiners ? (
                      <Link component="button" onClick={() => open(row.joiners_segment, `Joiners · ${row.label}`)}>
                        +{row.joiners}
                      </Link>
                    ) : (
                      0
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {row.exits ? (
                      <Link component="button" onClick={() => open(row.exits_segment, `Exits · ${row.label}`)}>
                        −{row.exits}
                      </Link>
                    ) : (
                      0
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {row.closing}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ContentCard>

        <Grid container spacing={1.5}>
          {(
            [
              ['department', 'By department'],
              ['designation', 'By designation'],
              ['employment_type', 'By employment type'],
              ['shift', 'By shift (today)'],
              ['manager', 'By reporting manager'],
            ] as const
          ).map(([key, title]) => (
            <Grid key={key} size={{ xs: 12, md: 6, lg: 4 }}>
              <ContentCard title={title}>
                <BreakdownList
                  rows={data.breakdowns[key]}
                  total={population}
                  emptyText="No employees for the current filters."
                  onSelect={(row) => open(row.segment, `${title.replace('By ', '')}: ${row.label}`)}
                />
              </ContentCard>
            </Grid>
          ))}
          <Grid size={{ xs: 12, md: 6, lg: 4 }}>
            <ContentCard title="Tenure">
              <BreakdownList
                rows={data.tenure}
                total={population}
                emptyText="No employees for the current filters."
                onSelect={(row) => open(row.segment, `Tenure: ${row.label}`)}
              />
            </ContentCard>
          </Grid>
        </Grid>

        <ContentCard
          title="Joiners & onboarding readiness"
          subtitle="Joiners in the period and upcoming joiners, with checklist progress and IT provisioning."
        >
          {data.joiners.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No joiners in this period or the next {data.horizon_days} days.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Employee</TableCell>
                  <TableCell>Joining</TableCell>
                  <TableCell>Manager</TableCell>
                  <TableCell>Onboarding</TableCell>
                  <TableCell>IT request</TableCell>
                  <TableCell>Virtual seat</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.joiners.map((row) => (
                  <TableRow key={row.user_id}>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {row.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {[row.designation, row.department].filter(Boolean).join(' · ') || '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>{formatDate(row.joining_date) || '—'}</TableCell>
                    <TableCell>{row.manager || <Chip size="small" color="warning" label="No manager" />}</TableCell>
                    <TableCell sx={{ minWidth: 160 }}>
                      {row.onboarding ? (
                        <Stack spacing={0.5}>
                          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Typography variant="caption">{row.onboarding.percent_complete}%</Typography>
                            {row.onboarding.overdue ? <Chip size="small" color="error" label="Overdue" /> : null}
                            {row.onboarding.status === 'completed' ? (
                              <TaskAltRoundedIcon fontSize="small" color="success" />
                            ) : null}
                          </Stack>
                          <LinearProgress variant="determinate" value={row.onboarding.percent_complete} />
                        </Stack>
                      ) : (
                        <Chip size="small" variant="outlined" label="No checklist" />
                      )}
                    </TableCell>
                    <TableCell>
                      {row.it?.status ? (
                        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                          <Chip size="small" label={row.it.status.replace(/_/g, ' ')} />
                          {row.it.overdue ? <Chip size="small" color="error" label="Overdue" /> : null}
                        </Stack>
                      ) : (
                        <Chip size="small" color="warning" variant="outlined" label="Not raised" />
                      )}
                    </TableCell>
                    <TableCell>{row.it?.seat_code || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>

        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, md: 6 }}>
            <ContentCard
              title={`Performance reviews · ${data.performance.review_year_label}`}
              subtitle={`${data.performance.sheets} review sheet(s) for active employees in the current cycle.`}
            >
              <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
                {data.performance.stages.map((stage) => (
                  <Chip
                    key={stage.key}
                    label={`${stage.label}: ${stage.count}`}
                    variant="outlined"
                    onClick={stage.count ? () => open(stage.segment, `Reviews · ${stage.label}`) : undefined}
                  />
                ))}
              </Stack>
              <Stack direction="row" spacing={1}>
                <Chip
                  color={data.performance.overdue ? 'error' : 'default'}
                  label={`Past due: ${data.performance.overdue}`}
                  onClick={data.performance.overdue ? () => open('review_overdue', 'Reviews past due') : undefined}
                />
                <Chip
                  color={data.performance.missing ? 'warning' : 'default'}
                  label={`No review sheet: ${data.performance.missing}`}
                  onClick={data.performance.missing ? () => open('review_missing', 'Active employees with no review sheet') : undefined}
                />
                <Link component={RouterLink} to="/performance/reviews" sx={{ alignSelf: 'center' }}>
                  Open reviews
                </Link>
              </Stack>
            </ContentCard>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <ContentCard
              title={`Work anniversaries (next ${data.horizon_days} days)`}
              subtitle="From joining dates. Birthdays are not shown — no date of birth is stored."
            >
              {data.milestones.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No work anniversaries in this window.
                </Typography>
              ) : (
                <Stack spacing={0.75}>
                  {data.milestones.map((m) => (
                    <Stack key={`${m.user_id}-${m.date}`} direction="row" sx={{ justifyContent: 'space-between' }}>
                      <Typography variant="body2">{m.name}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {formatDate(m.date)} · {m.years} yr{m.years === 1 ? '' : 's'}
                      </Typography>
                    </Stack>
                  ))}
                </Stack>
              )}
            </ContentCard>
          </Grid>
        </Grid>

        <ContentCard
          title="Timesheet follow-up"
          subtitle="Team members with 3+ missing working days or a draft timesheet (your assigned teams)."
        >
          {timesheetQuery.isLoading ? (
            <Typography variant="body2" color="text.secondary">
              Loading…
            </Typography>
          ) : attention.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Nobody needs timesheet follow-up.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Latest status</TableCell>
                  <TableCell align="right">Missing days</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {attention.slice(0, 15).map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.name}</TableCell>
                    <TableCell>{row.latest_timesheet_status}</TableCell>
                    <TableCell align="right">{row.missing_days}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>
      </Stack>

      <SegmentDialog drilldown={drilldown} filters={filters} onClose={() => setDrilldown(null)} />
    </PageContainer>
  );
}

export default HrDashboardPage;
