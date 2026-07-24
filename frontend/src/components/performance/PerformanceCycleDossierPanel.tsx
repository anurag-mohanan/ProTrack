import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Grid,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import HourglassEmptyOutlinedIcon from '@mui/icons-material/HourglassEmptyOutlined';
import BeachAccessOutlinedIcon from '@mui/icons-material/BeachAccessOutlined';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { designTokens } from '../../theme/designTokens';
import { useAuth } from '../../context/AuthContext';

type DossierProject = {
  project_id?: string | null;
  tool_number?: string | null;
  part_description?: string | null;
  customer_name?: string | null;
  assignment_role?: string | null;
  ownership_type?: string | null;
  hours_logged: number;
  quoted_hours?: number | null;
  actual_hours?: number | null;
  project_avq_variance_percent?: number | null;
  tasks_summary?: string | null;
};

type DossierPayload = {
  review_year: number;
  period_label: string;
  period_start: string;
  period_end: string;
  viewer_is_subject: boolean;
  leave_source_note: string;
  employee: {
    id: string;
    name: string;
    email: string;
    role?: string | null;
    joining_date?: string | null;
    company_experience?: string | null;
  };
  capacity: {
    worked_hours: number;
    expected_hours: number;
    capacity_percent?: number | null;
    productive_hours: number;
    non_productive_hours: number;
    leave_days: number;
    months_over_expected: number;
    months_in_period: number;
  };
  months: Array<{
    label: string;
    worked_hours: number;
    expected_hours: number;
    monthly_percent?: number | null;
    leave_days: number;
  }>;
  projects: {
    owned_count: number;
    supported_count: number;
    checking_hours: number;
    owned: DossierProject[];
    supported: DossierProject[];
  };
  prior_review?: {
    period_label?: string;
    overall_score?: number | null;
    career_goals?: string | null;
    strengths_summary?: string | null;
    improvement_summary?: string | null;
    manager_summary?: string | null;
  } | null;
  skills: { rated_count: number; proficient_or_expert: number };
};

type RosterRow = {
  user_id: string;
  name: string;
  email: string;
  role?: string | null;
  worked_hours: number;
  expected_hours: number;
  capacity_percent?: number | null;
  leave_days: number;
  months_over_expected: number;
  project_count: number;
  prior_score?: number | null;
  prior_period_label?: string | null;
};

function currentReviewYear(asOf = new Date()): number {
  return asOf.getFullYear();
}

function ProjectTable({ title, rows }: { title: string; rows: DossierProject[] }) {
  if (!rows.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        No {title.toLowerCase()} in this cycle.
      </Typography>
    );
  }
  return (
    <Box sx={{ mb: 2.5 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
        {title}
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Tool #</TableCell>
            <TableCell>Role</TableCell>
            <TableCell align="right">Your hours</TableCell>
            <TableCell align="right">Quoted</TableCell>
            <TableCell align="right">Actual</TableCell>
            <TableCell align="right">A vs Q %</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={`${row.project_id}-${row.tool_number}`}>
              <TableCell>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {row.tool_number || '—'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {[row.customer_name, row.part_description].filter(Boolean).join(' · ')}
                </Typography>
              </TableCell>
              <TableCell>{row.assignment_role || '—'}</TableCell>
              <TableCell align="right">{row.hours_logged.toFixed(1)}</TableCell>
              <TableCell align="right">
                {row.quoted_hours != null ? row.quoted_hours.toFixed(1) : '—'}
              </TableCell>
              <TableCell align="right">
                {row.actual_hours != null ? row.actual_hours.toFixed(1) : '—'}
              </TableCell>
              <TableCell align="right">
                {row.project_avq_variance_percent != null
                  ? `${row.project_avq_variance_percent}%`
                  : '—'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

function DossierDetail({
  userId,
  reviewYear,
  onBack,
}: {
  userId?: string;
  reviewYear: number;
  onBack?: () => void;
}) {
  const query = useQuery({
    queryKey: ['performance', 'dossier', userId ?? 'me', reviewYear],
    queryFn: async () =>
      (
        await apiClient.get<DossierPayload>('/hr/performance/dossier', {
          params: {
            review_year: reviewYear,
            ...(userId ? { user_id: userId } : {}),
          },
        })
      ).data,
  });

  if (query.isLoading) return <LoadingState message="Loading cycle dossier…" />;
  if (query.isError || !query.data) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load cycle dossier"
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const cap = data.capacity;

  return (
    <Stack spacing={2}>
      {onBack ? (
        <Button
          size="small"
          startIcon={<ArrowBackRoundedIcon />}
          onClick={onBack}
          sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
        >
          Team roster
        </Button>
      ) : null}
      <Box>
        <Typography variant="h6" sx={{ fontWeight: 800 }}>
          {data.employee.name}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {[data.employee.role, data.employee.company_experience, data.period_label]
            .filter(Boolean)
            .join(' · ')}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
          {data.period_start} → {data.period_end}
        </Typography>
      </Box>

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Capacity"
            value={cap.capacity_percent != null ? `${cap.capacity_percent}%` : '—'}
            subtitle={`${cap.worked_hours.toFixed(0)}h / ${cap.expected_hours.toFixed(0)}h`}
            icon={HourglassEmptyOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Months over expected"
            value={String(cap.months_over_expected)}
            subtitle={`of ${cap.months_in_period} months`}
            icon={TaskAltOutlinedIcon}
            accent={cap.months_over_expected ? 'warning' : undefined}
            compact
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Leave days"
            value={String(cap.leave_days)}
            subtitle="From timesheets"
            icon={BeachAccessOutlinedIcon}
            compact
          />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <KpiMetricCard
            title="Projects"
            value={String(data.projects.owned_count + data.projects.supported_count)}
            subtitle={`${data.projects.checking_hours.toFixed(0)}h checking`}
            icon={FolderOutlinedIcon}
            compact
          />
        </Grid>
      </Grid>

      <Typography variant="caption" color="text.secondary">
        {data.leave_source_note}
      </Typography>

      <Box
        sx={{
          p: 2,
          borderRadius: `${designTokens.radius.lg}px`,
          border: 1,
          borderColor: 'divider',
          bgcolor: designTokens.semantic.card,
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
          Prior acknowledged review
        </Typography>
        {data.prior_review ? (
          <Stack spacing={1}>
            <Typography variant="body2">
              <strong>{data.prior_review.period_label || 'Prior cycle'}</strong>
              {data.prior_review.overall_score != null
                ? ` · score ${data.prior_review.overall_score}`
                : ''}
            </Typography>
            {data.prior_review.career_goals ? (
              <Typography variant="body2">
                <strong>Goals:</strong> {data.prior_review.career_goals}
              </Typography>
            ) : null}
            {data.prior_review.strengths_summary ? (
              <Typography variant="body2">
                <strong>Strengths:</strong> {data.prior_review.strengths_summary}
              </Typography>
            ) : null}
            {data.prior_review.improvement_summary ? (
              <Typography variant="body2">
                <strong>Improvements:</strong> {data.prior_review.improvement_summary}
              </Typography>
            ) : null}
            {data.prior_review.manager_summary ? (
              <Typography variant="body2" color="text.secondary">
                Manager: {data.prior_review.manager_summary}
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No acknowledged annual review on file for this cycle window.
          </Typography>
        )}
      </Box>

      <ProjectTable title="Owned projects" rows={data.projects.owned} />
      <ProjectTable title="Supported projects" rows={data.projects.supported} />

      <Box
        sx={{
          p: 2,
          borderRadius: `${designTokens.radius.lg}px`,
          border: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
          Monthly capacity
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Month</TableCell>
              <TableCell align="right">Worked</TableCell>
              <TableCell align="right">Expected</TableCell>
              <TableCell align="right">%</TableCell>
              <TableCell align="right">Leave days</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.months.map((row) => (
              <TableRow key={row.label}>
                <TableCell>{row.label}</TableCell>
                <TableCell align="right">{Number(row.worked_hours).toFixed(1)}</TableCell>
                <TableCell align="right">{Number(row.expected_hours).toFixed(1)}</TableCell>
                <TableCell align="right">
                  {row.monthly_percent != null ? `${row.monthly_percent}%` : '—'}
                </TableCell>
                <TableCell align="right">{Number(row.leave_days).toFixed(1)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>

      <Typography variant="body2" color="text.secondary">
        Skills rated: {data.skills.rated_count} · Proficient/Expert:{' '}
        {data.skills.proficient_or_expert}
      </Typography>
    </Stack>
  );
}

export function PerformanceCycleDossierPanel() {
  const { user } = useAuth();
  const [reviewYear, setReviewYear] = useState(() => currentReviewYear());
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const yearOptions = useMemo(() => {
    const y = currentReviewYear();
    return [y, y - 1, y - 2];
  }, []);

  const rosterQuery = useQuery({
    queryKey: ['performance', 'dossier-roster', reviewYear],
    queryFn: async () =>
      (
        await apiClient.get<{ review_year: number; items: RosterRow[] }>(
          '/hr/performance/dossier-roster',
          { params: { review_year: reviewYear } },
        )
      ).data,
  });

  const showRoster =
    (rosterQuery.data?.items?.length ?? 0) > 1 ||
    ((rosterQuery.data?.items?.length ?? 0) === 1 &&
      rosterQuery.data?.items[0]?.user_id !== user?.id);

  if (selectedUserId || !showRoster) {
    return (
      <Stack spacing={2}>
        <TextField
          select
          size="small"
          label="Review year"
          value={reviewYear}
          onChange={(event) => setReviewYear(Number(event.target.value))}
          sx={{ maxWidth: 200 }}
        >
          {yearOptions.map((year) => (
            <MenuItem key={year} value={year}>
              FY {year - 1}-{String(year).slice(-2)} (ends Jun {year})
            </MenuItem>
          ))}
        </TextField>
        <DossierDetail
          userId={selectedUserId || undefined}
          reviewYear={reviewYear}
          onBack={
            showRoster && selectedUserId
              ? () => setSelectedUserId(null)
              : undefined
          }
        />
      </Stack>
    );
  }

  if (rosterQuery.isLoading) return <LoadingState message="Loading team cycle roster…" />;
  if (rosterQuery.isError) {
    return (
      <ErrorState
        error={rosterQuery.error}
        title="Unable to load team roster"
        onRetry={() => void rosterQuery.refetch()}
      />
    );
  }

  const items = rosterQuery.data?.items ?? [];

  return (
    <Stack spacing={2}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
      >
        <Typography variant="body2" color="text.secondary">
          July–June cycle headlines for people in your managed scope. Open a row for the full
          dossier (projects, capacity months, prior goals).
        </Typography>
        <TextField
          select
          size="small"
          label="Review year"
          value={reviewYear}
          onChange={(event) => setReviewYear(Number(event.target.value))}
          sx={{ minWidth: 220 }}
        >
          {yearOptions.map((year) => (
            <MenuItem key={year} value={year}>
              FY {year - 1}-{String(year).slice(-2)}
            </MenuItem>
          ))}
        </TextField>
      </Stack>

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Employee</TableCell>
            <TableCell align="right">Capacity %</TableCell>
            <TableCell align="right">Leave days</TableCell>
            <TableCell align="right">Months over</TableCell>
            <TableCell align="right">Projects</TableCell>
            <TableCell align="right">Prior score</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((row) => (
            <TableRow key={row.user_id} hover>
              <TableCell>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {row.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {row.role || row.email}
                </Typography>
              </TableCell>
              <TableCell align="right">
                {row.capacity_percent != null ? `${row.capacity_percent}%` : '—'}
              </TableCell>
              <TableCell align="right">{row.leave_days}</TableCell>
              <TableCell align="right">{row.months_over_expected}</TableCell>
              <TableCell align="right">{row.project_count}</TableCell>
              <TableCell align="right">
                {row.prior_score != null ? row.prior_score : '—'}
              </TableCell>
              <TableCell align="right">
                <Button
                  size="small"
                  onClick={() => setSelectedUserId(row.user_id)}
                  sx={{ textTransform: 'none' }}
                >
                  Open
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!items.length ? (
        <Typography color="text.secondary" variant="body2">
          No people in managed scope for this cycle.
        </Typography>
      ) : null}
    </Stack>
  );
}
