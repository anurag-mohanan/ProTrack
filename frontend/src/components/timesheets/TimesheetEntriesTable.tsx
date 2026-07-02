import { useMemo, useState } from 'react';
import {
  Box,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import type { Timesheet, TimesheetEntry } from '../../types';
import { TimesheetStatusChip } from '../common/StatusChip';
import { EmptyState } from '../common/EmptyState';
import { formatCellValue, formatDate, formatNumber } from '../../utils/format';

type SortKey = 'entry_date' | 'tool' | 'hours';
type SortDirection = 'asc' | 'desc';

interface TimesheetEntriesTableProps {
  monthLabel: string;
  entries: TimesheetEntry[];
  timesheetById: Map<string, Timesheet>;
  dailyTotals: Map<string, number>;
  dailyLimit: number;
  readOnly: boolean;
  deletingId: string | null;
  onEdit: (entry: TimesheetEntry) => void;
  onDelete: (entry: TimesheetEntry) => void;
  isEntryEditable: (entry: TimesheetEntry) => boolean;
}

function entryToolLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_code) || '—';
  }
  return formatCellValue(entry.project_tool_number) || '—';
}

function entryDescription(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_description) || 'Non-Productive';
  }
  return formatCellValue(entry.project_code ?? entry.customer_name) || '—';
}

function entryTaskLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_description) || '—';
  }
  return formatCellValue(entry.task_type_name) || '—';
}

export function TimesheetEntriesTable({
  monthLabel,
  entries,
  timesheetById,
  dailyTotals,
  dailyLimit,
  readOnly,
  deletingId,
  onEdit,
  onDelete,
  isEntryEditable,
}: TimesheetEntriesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('entry_date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const sortedEntries = useMemo(() => {
    const copy = [...entries];
    copy.sort((left, right) => {
      let compare = 0;
      if (sortKey === 'entry_date') {
        compare = left.entry_date.localeCompare(right.entry_date);
      } else if (sortKey === 'tool') {
        compare = entryToolLabel(left).localeCompare(entryToolLabel(right));
      } else {
        compare = Number(left.hours) - Number(right.hours);
      }
      return sortDirection === 'asc' ? compare : -compare;
    });
    return copy;
  }, [entries, sortDirection, sortKey]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDirection('asc');
  };

  const dailySubtotals = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entry of entries) {
      counts.set(entry.entry_date, (counts.get(entry.entry_date) ?? 0) + 1);
    }
    return counts;
  }, [entries]);

  return (
    <Box>
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
        Entries for {monthLabel}
      </Typography>

      {!entries.length ? (
        <EmptyState
          title="No entries yet"
          description="Use the form above to add your first timesheet entry for this month."
        />
      ) : (
        <TableContainer component={Paper} sx={{ borderRadius: 2, border: 1, borderColor: 'divider' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sortDirection={sortKey === 'entry_date' ? sortDirection : false}>
                  <TableSortLabel
                    active={sortKey === 'entry_date'}
                    direction={sortKey === 'entry_date' ? sortDirection : 'asc'}
                    onClick={() => handleSort('entry_date')}
                  >
                    Date
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={sortKey === 'tool' ? sortDirection : false}>
                  <TableSortLabel
                    active={sortKey === 'tool'}
                    direction={sortKey === 'tool' ? sortDirection : 'asc'}
                    onClick={() => handleSort('tool')}
                  >
                    Tool Number / NP Code
                  </TableSortLabel>
                </TableCell>
                <TableCell>Project Description</TableCell>
                <TableCell>Task</TableCell>
                <TableCell sortDirection={sortKey === 'hours' ? sortDirection : false} align="right">
                  <TableSortLabel
                    active={sortKey === 'hours'}
                    direction={sortKey === 'hours' ? sortDirection : 'asc'}
                    onClick={() => handleSort('hours')}
                  >
                    Hours
                  </TableSortLabel>
                </TableCell>
                <TableCell>Notes</TableCell>
                <TableCell>Billable</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedEntries.map((entry) => {
                const editable = !readOnly && isEntryEditable(entry);
                const dayTotal = dailyTotals.get(entry.entry_date) ?? 0;
                const showDayTotal = (dailySubtotals.get(entry.entry_date) ?? 0) > 1;
                const dayOverLimit = dayTotal > dailyLimit;
                const sheet = timesheetById.get(entry.timesheet_id);

                return (
                  <TableRow
                    key={entry.id}
                    hover
                    sx={dayOverLimit ? { bgcolor: 'warning.50' } : undefined}
                  >
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>
                      {formatDate(entry.entry_date)}
                      {showDayTotal ? (
                        <Typography
                          variant="caption"
                          color={dayOverLimit ? 'warning.main' : 'text.secondary'}
                          sx={{ display: 'block' }}
                        >
                          Day total: {formatNumber(dayTotal, 1)}
                        </Typography>
                      ) : null}
                    </TableCell>
                    <TableCell>{entryToolLabel(entry)}</TableCell>
                    <TableCell>{entryDescription(entry)}</TableCell>
                    <TableCell>{entryTaskLabel(entry)}</TableCell>
                    <TableCell align="right">{formatNumber(entry.hours, 1)}</TableCell>
                    <TableCell>{formatCellValue(entry.description) || '—'}</TableCell>
                    <TableCell>{entry.is_billable ? 'Yes' : 'No'}</TableCell>
                    <TableCell>
                      <TimesheetStatusChip status={sheet?.status ?? 'draft'} />
                    </TableCell>
                    <TableCell align="right">
                      {editable ? (
                        <Box sx={{ display: 'inline-flex', gap: 0.5 }}>
                          <Tooltip title="Edit">
                            <IconButton size="small" onClick={() => onEdit(entry)}>
                              <EditOutlinedIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete">
                            <IconButton
                              size="small"
                              color="error"
                              disabled={deletingId === entry.id}
                              onClick={() => onDelete(entry)}
                            >
                              <DeleteOutlineOutlinedIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
