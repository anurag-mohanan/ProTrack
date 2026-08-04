import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import type { Timesheet, TimesheetEntry } from '../../types';
import { TimesheetStatusChip } from '../common/StatusChip';
import { EmptyState } from '../common/EmptyState';
import { formatCellValue, formatDate, formatNumber } from '../../utils/format';

export interface OverviewUser {
  id: string;
  name: string;
  requiresTimesheet?: boolean;
  /** Designer's primary / section home team for cross-team badges. */
  homeTeamId?: string | null;
  entries?: TimesheetEntry[];
}

export interface TimesheetOverviewSection {
  title: string;
  subtitle?: string;
  emptyText?: string;
  /** When set, entries whose project team differs are flagged as other-team support. */
  teamId?: string | null;
  sectionKind?: string;
  users: OverviewUser[];
}

interface TimesheetUsersOverviewProps {
  sections: TimesheetOverviewSection[];
  timesheetById: Map<string, Timesheet>;
  periodStart?: string;
  periodEnd?: string;
  periodLabel?: string;
  onExportDesigner?: (userId: string, userName: string) => void | Promise<void>;
  exportingUserId?: string | null;
}

function toolLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_code) || '—';
  }
  return formatCellValue(entry.project_tool_number) || '—';
}

function taskLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_description) || '—';
  }
  return formatCellValue(entry.task_type_name) || '—';
}

function isOtherTeamSupport(
  entry: TimesheetEntry,
  homeTeamId: string | null | undefined,
): boolean {
  if (entry.work_category !== 'productive' || !entry.project_team_id || !homeTeamId) {
    return false;
  }
  return entry.project_team_id !== homeTeamId;
}

function otherTeamSupportHours(
  entries: TimesheetEntry[],
  homeTeamId: string | null | undefined,
): number {
  return entries.reduce((sum, entry) => {
    if (!isOtherTeamSupport(entry, homeTeamId)) return sum;
    return sum + Number(entry.hours);
  }, 0);
}

function UserEntries({
  entries,
  timesheetById,
  homeTeamId,
}: {
  entries: TimesheetEntry[];
  timesheetById: Map<string, Timesheet>;
  homeTeamId?: string | null;
}) {
  if (!entries.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
        No entries for this period.
      </Typography>
    );
  }

  const sorted = [...entries].sort((left, right) =>
    left.entry_date.localeCompare(right.entry_date),
  );

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Date</TableCell>
            <TableCell>Tool Number / NP Code</TableCell>
            <TableCell>Task</TableCell>
            <TableCell align="right">Hours</TableCell>
            <TableCell>Billable</TableCell>
            <TableCell>Notes</TableCell>
            <TableCell>Status</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map((entry) => {
            const otherTeam = isOtherTeamSupport(entry, homeTeamId);
            return (
              <TableRow key={entry.id}>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(entry.entry_date)}</TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                    <span>{toolLabel(entry)}</span>
                    {otherTeam ? (
                      <Chip
                        size="small"
                        color="info"
                        variant="outlined"
                        label={
                          entry.project_team_name
                            ? `Other team: ${entry.project_team_name}`
                            : 'Other team support'
                        }
                      />
                    ) : null}
                  </Box>
                </TableCell>
                <TableCell>{taskLabel(entry)}</TableCell>
                <TableCell align="right">{formatNumber(entry.hours, 1)}</TableCell>
                <TableCell>{entry.is_billable ? 'Yes' : 'No'}</TableCell>
                <TableCell>{formatCellValue(entry.description) || '—'}</TableCell>
                <TableCell>
                  <TimesheetStatusChip
                    status={timesheetById.get(entry.timesheet_id)?.status ?? 'draft'}
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function TimesheetUsersOverview({
  sections,
  timesheetById,
  periodLabel,
  onExportDesigner,
  exportingUserId,
}: TimesheetUsersOverviewProps) {
  return (
    <Box>
      {sections.map((section) => (
        <Box key={section.title} sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.25 }}>
            {section.title}
          </Typography>
          {section.subtitle ? (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.25 }}>
              {section.subtitle}
            </Typography>
          ) : null}

          {section.users.length === 0 ? (
            <EmptyState
              title={section.emptyText ?? 'No users'}
              description="There are no users to display in this section."
            />
          ) : (
            section.users.map((overviewUser) => {
              const entries = overviewUser.entries ?? [];
              const totalHours = entries.reduce((sum, entry) => sum + Number(entry.hours), 0);
              const homeTeamId = overviewUser.homeTeamId ?? section.teamId ?? null;
              const supportHours = otherTeamSupportHours(entries, homeTeamId);
              const missingRequired =
                Boolean(overviewUser.requiresTimesheet) && totalHours <= 0;
              return (
                <Accordion
                  key={`${section.title}:${overviewUser.id}`}
                  disableGutters
                  elevation={0}
                  sx={{
                    border: 1,
                    borderColor: missingRequired ? 'warning.main' : 'divider',
                    borderRadius: '8px !important',
                    mb: 1,
                    '&:before': { display: 'none' },
                  }}
                >
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1.5,
                        flexWrap: 'wrap',
                        width: '100%',
                        pr: 1,
                      }}
                    >
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>
                        {overviewUser.name}
                      </Typography>
                      <Chip
                        size="small"
                        variant="outlined"
                        label={`${entries.length} ${entries.length === 1 ? 'entry' : 'entries'}`}
                      />
                      <Chip
                        size="small"
                        color={totalHours > 0 ? 'primary' : 'default'}
                        variant="outlined"
                        label={`${formatNumber(totalHours, 1)} h`}
                      />
                      {supportHours > 0 ? (
                        <Chip
                          size="small"
                          color="info"
                          variant="outlined"
                          label={`${formatNumber(supportHours, 1)} h other-team support`}
                        />
                      ) : null}
                      {missingRequired ? (
                        <Chip size="small" color="warning" label="No hours this period" />
                      ) : null}
                      {onExportDesigner ? (
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<FileDownloadOutlinedIcon />}
                          disabled={exportingUserId === overviewUser.id}
                          onClick={(event) => {
                            event.stopPropagation();
                            void onExportDesigner(overviewUser.id, overviewUser.name);
                          }}
                          sx={{ ml: 'auto' }}
                        >
                          {exportingUserId === overviewUser.id
                            ? 'Exporting…'
                            : periodLabel
                              ? `Export ${periodLabel}`
                              : 'Export'}
                        </Button>
                      ) : null}
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails sx={{ pt: 0 }}>
                    <UserEntries
                      entries={entries}
                      timesheetById={timesheetById}
                      homeTeamId={homeTeamId}
                    />
                  </AccordionDetails>
                </Accordion>
              );
            })
          )}
        </Box>
      ))}
    </Box>
  );
}
