import { useState, type ReactNode } from 'react';
import {
  Box,
  Button,
  Chip,
  Collapse,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  alpha,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import PendingActionsRoundedIcon from '@mui/icons-material/PendingActionsRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import ViewModuleRoundedIcon from '@mui/icons-material/ViewModuleRounded';
import ViewListRoundedIcon from '@mui/icons-material/ViewListRounded';
import { useTheme } from '@mui/material/styles';
import { designTokens } from '../../theme/designTokens';
import { FilterSelect } from '../ui/design-system/FilterSelect';
import { KpiMetricCard } from '../ui/design-system/KpiMetricCard';
import { formatDate } from '../../utils/format';
import type { PerformanceReview } from '../../types/PerformanceReview';
import {
  getReviewDisplayStatus,
  reviewActionLabel,
  reviewPeriodLabel,
  reviewYearFromReview,
  type StatusQuickFilter,
} from '../../utils/performanceReviewListing';

export type FormListViewMode = 'cards' | 'list';

interface YearSelectorProps {
  years: number[];
  value: number | 'all';
  onChange: (value: number | 'all') => void;
}

export function FormYearSelector({ years, value, onChange }: YearSelectorProps) {
  return (
    <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', alignItems: 'center' }}>
      <Chip
        label="All years"
        clickable
        color={value === 'all' ? 'primary' : 'default'}
        variant={value === 'all' ? 'filled' : 'outlined'}
        onClick={() => onChange('all')}
      />
      {years.map((year) => (
        <Chip
          key={year}
          label={year}
          clickable
          color={value === year ? 'primary' : 'default'}
          variant={value === year ? 'filled' : 'outlined'}
          onClick={() => onChange(year)}
        />
      ))}
    </Stack>
  );
}

interface FormStatusQuickFiltersProps {
  value: StatusQuickFilter;
  onChange: (value: StatusQuickFilter) => void;
}

export function FormStatusQuickFilters({ value, onChange }: FormStatusQuickFiltersProps) {
  const options: Array<{ id: StatusQuickFilter; label: string }> = [
    { id: 'all', label: 'All' },
    { id: 'not_started', label: 'Not started' },
    { id: 'in_progress', label: 'In progress' },
    { id: 'pending_review', label: 'Pending review' },
    { id: 'completed', label: 'Completed' },
    { id: 'overdue', label: 'Overdue' },
  ];
  return (
    <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap' }}>
      {options.map((option) => (
        <Chip
          key={option.id}
          label={option.label}
          clickable
          size="small"
          color={value === option.id ? 'primary' : 'default'}
          variant={value === option.id ? 'filled' : 'outlined'}
          onClick={() => onChange(option.id)}
        />
      ))}
    </Stack>
  );
}

interface FormListingFiltersProps {
  teamOptions: Array<{ id: string; name: string }>;
  departmentOptions: string[];
  teamId: string;
  department: string;
  search: string;
  needsActionOnly: boolean;
  onTeamChange: (teamId: string) => void;
  onDepartmentChange: (department: string) => void;
  onSearchChange: (search: string) => void;
  onNeedsActionChange: (value: boolean) => void;
}

export function FormListingFilters({
  teamOptions,
  departmentOptions,
  teamId,
  department,
  search,
  needsActionOnly,
  onTeamChange,
  onDepartmentChange,
  onSearchChange,
  onNeedsActionChange,
}: FormListingFiltersProps) {
  return (
    <Grid container spacing={1.5}>
      <Grid size={{ xs: 12, md: 3 }}>
        <FilterSelect label="Team" value={teamId} onChange={(e) => onTeamChange(String(e.target.value))}>
          <MenuItem value="">All authorized teams</MenuItem>
          {teamOptions.map((team) => (
            <MenuItem key={team.id} value={team.id}>{team.name}</MenuItem>
          ))}
        </FilterSelect>
      </Grid>
      <Grid size={{ xs: 12, md: 3 }}>
        <FilterSelect
          label="Department"
          value={department}
          onChange={(e) => onDepartmentChange(String(e.target.value))}
        >
          <MenuItem value="">All departments</MenuItem>
          {departmentOptions.map((dept) => (
            <MenuItem key={dept} value={dept}>{dept}</MenuItem>
          ))}
        </FilterSelect>
      </Grid>
      <Grid size={{ xs: 12, md: 4 }}>
        <TextField
          fullWidth
          size="small"
          label="Search"
          placeholder="Employee, team, department, year…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </Grid>
      <Grid size={{ xs: 12, md: 2 }}>
        <Button
          fullWidth
          variant={needsActionOnly ? 'contained' : 'outlined'}
          onClick={() => onNeedsActionChange(!needsActionOnly)}
          sx={{ height: 40 }}
        >
          Needs my action
        </Button>
      </Grid>
    </Grid>
  );
}

interface FormYearSummaryProps {
  year: number;
  total: number;
  completed: number;
  inProgress: number;
  pending: number;
  overdue: number;
}

export function FormYearSummary({
  year,
  total,
  completed,
  inProgress,
  pending,
  overdue,
}: FormYearSummaryProps) {
  const completion = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <Paper
      variant="outlined"
      sx={{ p: 2, borderRadius: 2, mb: 2 }}
    >
      <Typography variant="h6" sx={{ fontWeight: 800, mb: 1.5 }}>{year}</Typography>
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <KpiMetricCard compact title="Total" value={String(total)} icon={AssessmentOutlinedIcon} />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <KpiMetricCard compact title="Completed" value={String(completed)} accent="success" icon={CheckCircleOutlineRoundedIcon} />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <KpiMetricCard compact title="In progress" value={String(inProgress)} accent="info" icon={PendingActionsRoundedIcon} />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <KpiMetricCard compact title="Completion" value={`${completion}%`} accent="primary" icon={TrendingUpRoundedIcon} />
        </Grid>
      </Grid>
      <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap' }}>
        <Chip size="small" label={`${pending} pending review`} variant="outlined" />
        {overdue > 0 ? <Chip size="small" color="warning" label={`${overdue} overdue`} /> : null}
      </Stack>
    </Paper>
  );
}

interface FormReviewCardProps {
  review: PerformanceReview;
  userId?: string | null;
  onOpen: () => void;
}

export function FormReviewCard({ review, userId, onOpen }: FormReviewCardProps) {
  const theme = useTheme();
  const display = getReviewDisplayStatus(review);
  const year = reviewYearFromReview(review);
  const percent = review.completion_percent ?? 0;
  const actionLabel = reviewActionLabel(review, userId);
  const statusColor =
    display.category === 'completed'
      ? 'success'
      : display.category === 'overdue'
        ? 'warning'
        : display.category === 'pending_review'
          ? 'info'
          : 'default';

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderRadius: 2,
        transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
        '&:hover': {
          borderColor: alpha(theme.palette.primary.main, 0.4),
          boxShadow: designTokens.elevation.cardHover,
        },
      }}
    >
      <Stack spacing={1.25}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <Box>
            <Typography sx={{ fontWeight: 800, fontSize: 17 }}>{review.employee_name}</Typography>
            <Typography variant="body2" color="text.secondary">
              {review.team_name ?? '—'}
              {review.employee_department ? ` · ${review.employee_department}` : ''}
            </Typography>
          </Box>
          <Chip size="small" label={year} variant="outlined" />
        </Stack>

        <Typography variant="body2" color="text.secondary">
          Review period: {reviewPeriodLabel(review)}
        </Typography>

        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Chip size="small" label={display.label} color={statusColor} variant="outlined" />
          {display.category !== 'completed' ? (
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{percent}%</Typography>
          ) : null}
        </Stack>

        {display.category !== 'completed' ? (
          <LinearProgress variant="determinate" value={percent} sx={{ height: 6, borderRadius: 99 }} />
        ) : null}

        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            {review.updated_at
              ? `Updated ${formatDate(review.updated_at)}`
              : review.acknowledged_at
                ? `Completed ${formatDate(review.acknowledged_at)}`
                : '—'}
          </Typography>
          <Button size="small" variant="contained" onClick={onOpen}>{actionLabel}</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

interface FormYearCollapsibleSectionProps {
  year: number;
  count: number;
  defaultExpanded?: boolean;
  children: ReactNode;
}

export function FormYearCollapsibleSection({
  year,
  count,
  defaultExpanded = false,
  children,
}: FormYearCollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultExpanded);
  return (
    <Box sx={{ mb: 2 }}>
      <Stack
        direction="row"
        spacing={0.5}
        sx={{ mb: 1, cursor: 'pointer', alignItems: 'center' }}
        onClick={() => setOpen((value) => !value)}
      >
        <IconButton size="small" aria-label={`Toggle ${year}`}>
          <ExpandMoreRoundedIcon sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
        </IconButton>
        <Typography variant="h6" sx={{ fontWeight: 800 }}>{year}</Typography>
        <Chip size="small" label={`${count} reviews`} variant="outlined" />
      </Stack>
      <Collapse in={open}>{children}</Collapse>
    </Box>
  );
}

interface FormViewSwitcherProps {
  value: FormListViewMode;
  onChange: (value: FormListViewMode) => void;
}

export function FormViewSwitcher({ value, onChange }: FormViewSwitcherProps) {
  return (
    <ToggleButtonGroup
      size="small"
      value={value}
      exclusive
      onChange={(_, next) => next && onChange(next)}
    >
      <ToggleButton value="cards" aria-label="Card view">
        <ViewModuleRoundedIcon fontSize="small" sx={{ mr: 0.5 }} />
        Cards
      </ToggleButton>
      <ToggleButton value="list" aria-label="List view">
        <ViewListRoundedIcon fontSize="small" sx={{ mr: 0.5 }} />
        List
      </ToggleButton>
    </ToggleButtonGroup>
  );
}

interface FormEmptyStateProps {
  title: string;
  message: string;
  onClear?: () => void;
}

export function FormEmptyState({ title, message, onClear }: FormEmptyStateProps) {
  return (
    <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', borderRadius: 2 }}>
      <Typography variant="h6" sx={{ fontWeight: 800, mb: 1 }}>{title}</Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>{message}</Typography>
      {onClear ? (
        <Button variant="outlined" onClick={onClear}>Clear filters</Button>
      ) : null}
    </Paper>
  );
}
