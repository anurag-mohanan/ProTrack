import { useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Grid,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import type { SvgIconComponent } from '@mui/icons-material';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
import EngineeringRoundedIcon from '@mui/icons-material/EngineeringRounded';
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded';
import BadgeRoundedIcon from '@mui/icons-material/BadgeRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import QueryStatsRoundedIcon from '@mui/icons-material/QueryStatsRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import Inventory2RoundedIcon from '@mui/icons-material/Inventory2Rounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import PieChartRoundedIcon from '@mui/icons-material/PieChartRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import BeachAccessRoundedIcon from '@mui/icons-material/BeachAccessRounded';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import { apiClient } from '../api/client';
import { PageContainer } from '../components/common/PageContainer';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { ModernPageHeader } from '../components/ui/design-system';
import { designTokens } from '../theme/designTokens';

type CatalogItem = {
  title: string;
  path: string;
};

type CatalogCategory = {
  category: string;
  module?: string;
  items: CatalogItem[];
};

type ReportMeta = {
  description: string;
  icon: SvgIconComponent;
  comingSoon?: boolean;
};

const CATEGORY_META: Record<
  string,
  { icon: SvgIconComponent; accent: string; blurb: string }
> = {
  'Engineering Reports': {
    icon: EngineeringRoundedIcon,
    accent: designTokens.semantic.primary,
    blurb: 'Delivery, utilization, and timesheet operations',
  },
  'Financial Reports': {
    icon: AccountBalanceRoundedIcon,
    accent: '#0d9488',
    blurb: 'P&L, budgets, and commercial performance',
  },
  'HR Reports': {
    icon: BadgeRoundedIcon,
    accent: '#7c3aed',
    blurb: 'People productivity and compliance signals',
  },
};

const REPORT_META: Record<string, ReportMeta> = {
  'Engineering Reports Suite': {
    description: 'Unified engineering overview across projects, stages, and hours.',
    icon: InsightsRoundedIcon,
  },
  'Productivity Reports': {
    description: 'Billable vs non-productive mix and designer throughput.',
    icon: QueryStatsRoundedIcon,
  },
  'Resource Reports': {
    description: 'Capacity, allocation, and team load across the portfolio.',
    icon: GroupsRoundedIcon,
  },
  'Timesheet Reports': {
    description: 'Weekly submissions, exports, and hours by category.',
    icon: ScheduleRoundedIcon,
  },
  'Customer Reports': {
    description: 'Customer-facing hour summaries and engagement views.',
    icon: Inventory2RoundedIcon,
  },
  'Customer Timesheet Pack': {
    description: 'Packaged timesheet export ready for customer share-out.',
    icon: Inventory2RoundedIcon,
  },
  'Profit & Loss': {
    description: 'Company and team P&L with period comparison.',
    icon: PieChartRoundedIcon,
  },
  'Project Profitability': {
    description: 'Margin and cost recovery by project and customer.',
    icon: TrendingUpRoundedIcon,
  },
  'Budget vs Actual': {
    description: 'Track spend against approved budgets and fee bands.',
    icon: AccountBalanceRoundedIcon,
  },
  'Revenue Trend': {
    description: 'Quoted, invoiced, and collected revenue over time.',
    icon: TrendingUpRoundedIcon,
  },
  'AI Insights (placeholders)': {
    description: 'Suggested anomalies and narrative insights (coming soon).',
    icon: AutoAwesomeRoundedIcon,
    comingSoon: true,
  },
  'AI Insights (placeholder)': {
    description: 'Suggested anomalies and narrative insights (coming soon).',
    icon: AutoAwesomeRoundedIcon,
    comingSoon: true,
  },
  'Team Productivity': {
    description: 'Team-level hours, utilization, and follow-up queues.',
    icon: GroupsRoundedIcon,
  },
  'Timesheet Completion': {
    description: 'Who is current, late, or missing timesheet entries.',
    icon: HowToRegRoundedIcon,
  },
  'Leave (future)': {
    description: 'Leave balances and patterns — planned after GreytHR sync.',
    icon: BeachAccessRoundedIcon,
    comingSoon: true,
  },
  'Attendance (future)': {
    description: 'Attendance overview — planned after HRIS integration.',
    icon: HowToRegRoundedIcon,
    comingSoon: true,
  },
};

function resolveMeta(title: string): ReportMeta {
  const exact = REPORT_META[title];
  if (exact) return exact;
  const lower = title.toLowerCase();
  const comingSoon = lower.includes('future') || lower.includes('placeholder');
  return {
    description: comingSoon
      ? 'Planned report — not available in this release.'
      : 'Open this report in its source module.',
    icon: InsightsRoundedIcon,
    comingSoon,
  };
}

function ReportTile({
  item,
  accent,
}: {
  item: CatalogItem;
  accent: string;
}) {
  const theme = useTheme();
  const meta = resolveMeta(item.title);
  const Icon = meta.icon;
  const disabled = Boolean(meta.comingSoon);

  return (
    <Paper
      component={disabled ? 'div' : RouterLink}
      to={disabled ? undefined : item.path}
      elevation={0}
      sx={{
        height: '100%',
        textDecoration: 'none',
        color: 'inherit',
        display: 'flex',
        flexDirection: 'column',
        gap: 1.25,
        p: 2,
        borderRadius: `${designTokens.radius.lg}px`,
        border: `1px solid ${theme.palette.divider}`,
        bgcolor: designTokens.semantic.card,
        boxShadow: designTokens.elevation.card,
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.72 : 1,
        transition: `transform ${designTokens.motion.normal}, box-shadow ${designTokens.motion.normal}, border-color ${designTokens.motion.normal}`,
        '&:hover': disabled
          ? undefined
          : {
              transform: 'translateY(-2px)',
              boxShadow: designTokens.elevation.cardHover,
              borderColor: alpha(accent, 0.45),
              '& .report-arrow': { opacity: 1, transform: 'translateX(0)' },
            },
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: `${designTokens.radius.md}px`,
            display: 'grid',
            placeItems: 'center',
            bgcolor: alpha(accent, 0.1),
            color: accent,
            flexShrink: 0,
          }}
        >
          <Icon fontSize="small" />
        </Box>
        <Chip
          size="small"
          label={disabled ? 'Coming soon' : 'Available'}
          color={disabled ? 'default' : 'success'}
          variant={disabled ? 'outlined' : 'filled'}
          sx={{
            height: 22,
            fontSize: '0.6875rem',
            fontWeight: 600,
            ...(disabled
              ? {}
              : {
                  bgcolor: alpha(designTokens.semantic.success, 0.12),
                  color: designTokens.semantic.success,
                }),
          }}
        />
      </Stack>
      <Box sx={{ flex: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.3, mb: 0.5 }}>
          {item.title.replace(/\s*\((future|placeholders?)\)$/i, '')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.45 }}>
          {meta.description}
        </Typography>
      </Box>
      {!disabled ? (
        <Stack
          direction="row"
          spacing={0.5}
          className="report-arrow"
          sx={{
            alignItems: 'center',
            mt: 0.5,
            color: accent,
            fontWeight: 600,
            fontSize: '0.8125rem',
            opacity: 0.85,
            transform: 'translateX(-2px)',
            transition: `opacity ${designTokens.motion.fast}, transform ${designTokens.motion.fast}`,
          }}
        >
          <span>Open report</span>
          <ArrowForwardRoundedIcon sx={{ fontSize: 16 }} />
        </Stack>
      ) : null}
    </Paper>
  );
}

export function AnalyticsHubPage() {
  const theme = useTheme();
  const [search, setSearch] = useState('');
  const query = useQuery({
    queryKey: ['analytics-catalog'],
    queryFn: async () =>
      (await apiClient.get<{ categories: CatalogCategory[] }>('/analytics/catalog')).data,
  });

  const categories = query.data?.categories ?? [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return categories;
    return categories
      .map((category) => ({
        ...category,
        items: category.items.filter(
          (item) =>
            item.title.toLowerCase().includes(q) ||
            resolveMeta(item.title).description.toLowerCase().includes(q) ||
            category.category.toLowerCase().includes(q),
        ),
      }))
      .filter((category) => category.items.length > 0);
  }, [categories, search]);

  const totalReports = categories.reduce((sum, cat) => sum + cat.items.length, 0);
  const availableReports = categories.reduce(
    (sum, cat) =>
      sum + cat.items.filter((item) => !resolveMeta(item.title).comingSoon).length,
    0,
  );

  if (query.isLoading) return <LoadingState message="Loading analytics catalog…" />;
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        title="Could not load the reports catalog"
        onRetry={() => void query.refetch()}
      />
    );
  }

  return (
    <PageContainer>
      <ModernPageHeader
        title="Reports & Analytics"
        subtitle="Browse cross-module reports gated by your permissions. Open a tile to jump straight into the source workspace."
        summary={
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1.5}
            sx={{
              alignItems: { xs: 'stretch', sm: 'center' },
              justifyContent: 'space-between',
            }}
          >
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              <Chip
                icon={<InsightsRoundedIcon />}
                label={`${availableReports} available`}
                size="small"
                sx={{ fontWeight: 600 }}
              />
              <Chip
                label={`${totalReports} in catalog`}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 500 }}
              />
              <Chip
                label={`${categories.length} categories`}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 500 }}
              />
            </Stack>
            <TextField
              size="small"
              placeholder="Search reports…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              sx={{
                minWidth: { xs: '100%', sm: 280 },
                bgcolor: designTokens.semantic.card,
                '& .MuiOutlinedInput-root': {
                  borderRadius: `${designTokens.radius.md}px`,
                },
              }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchRoundedIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                },
              }}
            />
          </Stack>
        }
      />

      <Stack spacing={3}>
        {filtered.map((category) => {
          const meta = CATEGORY_META[category.category] ?? {
            icon: InsightsRoundedIcon,
            accent: theme.palette.primary.main,
            blurb: 'Reports in this module',
          };
          const CategoryIcon = meta.icon;

          return (
            <Box key={category.category}>
              <Stack
                direction="row"
                spacing={1.5}
                sx={{ mb: 1.75, alignItems: 'center' }}
              >
                <Box
                  sx={{
                    width: 44,
                    height: 44,
                    borderRadius: `${designTokens.radius.md}px`,
                    display: 'grid',
                    placeItems: 'center',
                    bgcolor: alpha(meta.accent, 0.12),
                    color: meta.accent,
                    border: `1px solid ${alpha(meta.accent, 0.2)}`,
                  }}
                >
                  <CategoryIcon fontSize="small" />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                    {category.category}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {meta.blurb} · {category.items.length} report
                    {category.items.length === 1 ? '' : 's'}
                  </Typography>
                </Box>
              </Stack>

              <Grid container spacing={1.75}>
                {category.items.map((item) => (
                  <Grid
                    key={`${category.category}-${item.title}`}
                    size={{ xs: 12, sm: 6, md: 4, lg: 3 }}
                  >
                    <ReportTile item={item} accent={meta.accent} />
                  </Grid>
                ))}
              </Grid>
            </Box>
          );
        })}

        {!filtered.length ? (
          <Paper
            elevation={0}
            sx={{
              p: 4,
              textAlign: 'center',
              borderRadius: `${designTokens.radius.lg}px`,
              border: `1px dashed ${theme.palette.divider}`,
              bgcolor: alpha(theme.palette.primary.main, 0.02),
            }}
          >
            <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
              {search.trim()
                ? 'No reports match your search'
                : 'No report categories available'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {search.trim()
                ? 'Try a different keyword, or clear the search to see the full catalog.'
                : 'Your role does not currently include report module permissions.'}
            </Typography>
          </Paper>
        ) : null}
      </Stack>
    </PageContainer>
  );
}

export default AnalyticsHubPage;
