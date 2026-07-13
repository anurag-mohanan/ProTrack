import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
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
import type { Timesheet, TimesheetEntry } from '../../types';
import { TimesheetStatusChip } from '../common/StatusChip';
import { EmptyState } from '../common/EmptyState';
import { formatCellValue, formatDate, formatNumber } from '../../utils/format';

export interface OverviewUser {
  id: string;
  name: string;
  requiresTimesheet?: boolean;
}

export interface TimesheetOverviewSection {
  title: string;
  subtitle?: string;
  emptyText?: string;
  users: OverviewUser[];
}

interface TimesheetUsersOverviewProps {
  sections: TimesheetOverviewSection[];
  entriesByUser: Map<string, TimesheetEntry[]>;
  timesheetById: Map<string, Timesheet>;
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

function UserEntries({
  entries,
  timesheetById,
}: {
  entries: TimesheetEntry[];
  timesheetById: Map<string, Timesheet>;
}) {
  if (!entries.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
        No entries for this month.
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
          {sorted.map((entry) => (
            <TableRow key={entry.id}>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(entry.entry_date)}</TableCell>
              <TableCell>{toolLabel(entry)}</TableCell>
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
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function TimesheetUsersOverview({
  sections,
  entriesByUser,
  timesheetById,
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
              const entries = entriesByUser.get(overviewUser.id) ?? [];
              const totalHours = entries.reduce((sum, entry) => sum + Number(entry.hours), 0);
              const missingRequired =
                Boolean(overviewUser.requiresTimesheet) && totalHours <= 0;
              return (
                <Accordion
                  key={overviewUser.id}
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
                      {missingRequired ? (
                        <Chip size="small" color="warning" label="No hours this month" />
                      ) : null}
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails sx={{ pt: 0 }}>
                    <UserEntries entries={entries} timesheetById={timesheetById} />
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
