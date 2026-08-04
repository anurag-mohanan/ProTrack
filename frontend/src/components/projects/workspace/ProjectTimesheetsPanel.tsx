import { useMemo } from 'react';
import { Box, Button, Chip, Stack, TableRow, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded';
import MoneyOffRoundedIcon from '@mui/icons-material/MoneyOffRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import PaidRoundedIcon from '@mui/icons-material/PaidRounded';
import { EmptyState } from '../../common/EmptyState';
import { ErrorState } from '../../common/ErrorState';
import { LoadingState } from '../../common/LoadingState';
import { KpiStrip } from '../../analytics/KpiStrip';
import {
  KpiMetricCard,
  OperationalDataTable,
  StickyHeaderCell,
  StickyTableCell,
} from '../../ui/design-system';
import { fetchAllTimesheetEntries } from '../../../api/timesheets';
import type { TimesheetEntry } from '../../../types';
import {
  CONTRIBUTION_REASON_LABELS,
  isReworkQualityReason,
  type ContributionReason,
} from '../../../types/TimesheetEntry';
import { designTokens } from '../../../theme/designTokens';
import { formatCellValue, formatDate, formatNumber, toFiniteNumber } from '../../../utils/format';
import {
  sortProjectTimesheetEntries,
  summarizeProjectTimesheetEntries,
} from '../../../utils/projectTimesheetSummary';

interface ProjectTimesheetsPanelProps {
  projectId: string;
  quotedHours?: number | string | null;
}

function entryTaskLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    if ((entry.leave_count ?? 0) > 0 || entry.non_productive_category === 'leave') {
      return 'Leave';
    }
    return formatCellValue(entry.non_productive_description) || 'Non-Productive';
  }
  return formatCellValue(entry.task_type_name) || '—';
}

function contributionLabel(reason: ContributionReason | null | undefined): string {
  if (!reason) return '—';
  return CONTRIBUTION_REASON_LABELS[reason] ?? reason;
}

export function ProjectTimesheetsPanel({
  projectId,
  quotedHours,
}: ProjectTimesheetsPanelProps) {
  const entriesQuery = useQuery({
    queryKey: ['timesheet-entries', 'project', projectId],
    queryFn: () => fetchAllTimesheetEntries({ project_id: projectId, limit: 2000 }),
  });

  const entries = useMemo(
    () => sortProjectTimesheetEntries(entriesQuery.data ?? []),
    [entriesQuery.data],
  );
  const summary = useMemo(() => summarizeProjectTimesheetEntries(entries), [entries]);
  const quoted = toFiniteNumber(quotedHours);
  const burnPct = quoted > 0 ? Math.round((summary.totalHours / quoted) * 100) : null;

  if (entriesQuery.isLoading) {
    return <LoadingState message="Loading project timesheets…" />;
  }
  if (entriesQuery.error) {
    return <ErrorState error={entriesQuery.error} />;
  }

  return (
    <Box>
      <KpiStrip columns={4}>
        <KpiMetricCard
          compact
          title="Total hours"
          value={formatNumber(summary.totalHours, 1) || '0'}
          subtitle={
            burnPct != null
              ? `${burnPct}% of ${formatNumber(quoted, 0) || '0'}h quoted`
              : `${summary.entryCount} line${summary.entryCount === 1 ? '' : 's'}`
          }
          icon={AccessTimeRoundedIcon}
          accent="primary"
        />
        <KpiMetricCard
          compact
          title="Billable hours"
          value={formatNumber(summary.billableHours, 1) || '0'}
          subtitle="Customer-billable productive time"
          icon={PaidRoundedIcon}
          accent="success"
        />
        <KpiMetricCard
          compact
          title="Rework (unbilled)"
          value={formatNumber(summary.reworkHours, 1) || '0'}
          subtitle={
            summary.unbilledHours > summary.reworkHours
              ? `${formatNumber(summary.unbilledHours, 1)}h unbilled total`
              : 'Quality / designer rework'
          }
          icon={MoneyOffRoundedIcon}
          accent={summary.reworkHours > 0 ? 'warning' : 'info'}
        />
        <KpiMetricCard
          compact
          title="Designers worked"
          value={String(summary.designerCount)}
          subtitle={
            summary.byDesigner[0]
              ? `Top: ${summary.byDesigner[0].userName}`
              : 'No time logged yet'
          }
          icon={GroupsRoundedIcon}
          accent="info"
        />
      </KpiStrip>

      {summary.byDesigner.length > 0 ? (
        <Box
          sx={{
            mt: 1.5,
            mb: 1.5,
            px: 1.5,
            py: 1,
            borderRadius: 2,
            border: 1,
            borderColor: 'divider',
            bgcolor: designTokens.semantic.card,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
            Hours by designer
          </Typography>
          <Stack direction="row" spacing={0.75} useFlexGap sx={{ mt: 0.75, flexWrap: 'wrap' }}>
            {summary.byDesigner.map((designer) => (
              <Chip
                key={designer.userId}
                size="small"
                label={`${designer.userName}: ${formatNumber(designer.hours, 1) || '0'}h${
                  designer.reworkHours > 0
                    ? ` · ${formatNumber(designer.reworkHours, 1)}h rework`
                    : ''
                }`}
                sx={{ fontWeight: 600 }}
              />
            ))}
          </Stack>
        </Box>
      ) : null}

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          mb: 1.25,
          flexWrap: 'wrap',
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Unbilled rework hours (quality issues) stay on the tool for design-efficiency analysis.
        </Typography>
        <Button component={RouterLink} to="/timesheets" size="small" variant="outlined">
          Open Timesheets
        </Button>
      </Box>

      {!entries.length ? (
        <EmptyState
          title="No timesheet entries"
          description="Time logged against this tool in the Timesheets module will appear here."
        />
      ) : (
        <>
          {entries.length >= 500 ? (
            <Typography variant="caption" color="warning.main" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
              Showing the first 500 lines. Refine in the Timesheets module if the project has more history.
            </Typography>
          ) : null}
          <OperationalDataTable
            maxHeight="calc(100vh - 360px)"
            head={
              <TableRow>
                <StickyHeaderCell pinned>Date</StickyHeaderCell>
                <StickyHeaderCell>Designer</StickyHeaderCell>
                <StickyHeaderCell>Task</StickyHeaderCell>
                <StickyHeaderCell>Description</StickyHeaderCell>
                <StickyHeaderCell>Contribution</StickyHeaderCell>
                <StickyHeaderCell>Billable</StickyHeaderCell>
                <StickyHeaderCell align="right">Hours</StickyHeaderCell>
              </TableRow>
            }
          >
            {entries.map((entry) => (
              <TableRow key={entry.id} hover>
                <StickyTableCell pinned>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {formatDate(entry.entry_date) || '—'}
                  </Typography>
                </StickyTableCell>
                <StickyTableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {formatCellValue(entry.user_name) || '—'}
                  </Typography>
                </StickyTableCell>
                <StickyTableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {entryTaskLabel(entry)}
                  </Typography>
                </StickyTableCell>
                <StickyTableCell>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      maxWidth: 280,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {formatCellValue(entry.description) || '—'}
                  </Typography>
                </StickyTableCell>
                <StickyTableCell>
                  <Typography
                    variant="body2"
                    color={
                      isReworkQualityReason(entry.contribution_reason)
                        ? 'warning.main'
                        : 'text.secondary'
                    }
                    sx={{
                      fontWeight: isReworkQualityReason(entry.contribution_reason) ? 700 : 400,
                    }}
                  >
                    {contributionLabel(entry.contribution_reason)}
                  </Typography>
                </StickyTableCell>
                <StickyTableCell>
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 700,
                      color: entry.is_billable ? 'success.main' : 'warning.main',
                    }}
                  >
                    {entry.is_billable ? 'Yes' : 'No'}
                  </Typography>
                </StickyTableCell>
                <StickyTableCell align="right">
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {formatNumber(toFiniteNumber(entry.hours), 2) || '0'}
                  </Typography>
                </StickyTableCell>
              </TableRow>
            ))}
          </OperationalDataTable>
        </>
      )}
    </Box>
  );
}
