import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  IconButton,
  TableRow,
  TableSortLabel,
  Tooltip,
  Typography,
} from '@mui/material';
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EditRoundedIcon from '@mui/icons-material/EditRounded';
import type { Timesheet, TimesheetEntry } from '../../types';
import { TimesheetStatusChip } from '../common/StatusChip';
import { EmptyState } from '../common/EmptyState';
import {
  ClickableTableRow,
  OperationalDataTable,
  StickyHeaderCell,
  StickyTableCell,
} from '../ui/design-system';
import { TimesheetToolCell, TimesheetWorkCategoryBadge } from './TimesheetEntryBadges';
import { designTokens } from '../../theme/designTokens';
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
  showUser?: boolean;
  deletingId: string | null;
  selectedEntryId: string | null;
  onSelect: (entry: TimesheetEntry | null) => void;
  onEdit: (entry: TimesheetEntry) => void;
  onDelete: (entry: TimesheetEntry) => void;
  onDuplicate?: (entry: TimesheetEntry) => void;
  isEntryEditable: (entry: TimesheetEntry) => boolean;
  onRequestDeleteSelected?: () => void;
}

function entryDescription(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_description) || 'Non-Productive';
  }
  return formatCellValue(entry.project_code ?? entry.customer_name) || '—';
}

function entryTaskLabel(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    if ((entry.leave_count ?? 0) > 0 || entry.non_productive_category === 'leave') {
      return 'Leave';
    }
    return formatCellValue(entry.non_productive_description) || '—';
  }
  return formatCellValue(entry.task_type_name) || '—';
}

function entryToolSortKey(entry: TimesheetEntry): string {
  if (entry.work_category === 'non_productive') {
    return formatCellValue(entry.non_productive_code) || '';
  }
  return formatCellValue(entry.project_tool_number) || '';
}

export function TimesheetEntriesTable({
  monthLabel,
  entries,
  timesheetById,
  dailyTotals,
  dailyLimit,
  readOnly,
  showUser = false,
  deletingId,
  selectedEntryId,
  onSelect,
  onEdit,
  onDelete,
  onDuplicate,
  isEntryEditable,
  onRequestDeleteSelected,
}: TimesheetEntriesTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('entry_date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' || readOnly || !selectedEntryId || !onRequestDeleteSelected) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      onRequestDeleteSelected();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onRequestDeleteSelected, readOnly, selectedEntryId]);

  const sortedEntries = useMemo(() => {
    const copy = [...entries];
    copy.sort((left, right) => {
      let compare = 0;
      if (sortKey === 'entry_date') {
        compare = left.entry_date.localeCompare(right.entry_date);
      } else if (sortKey === 'tool') {
        compare = entryToolSortKey(left).localeCompare(entryToolSortKey(right));
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

  const rowCategoryBg = (entry: TimesheetEntry) => {
    if ((entry.leave_count ?? 0) > 0 || entry.non_productive_category === 'leave') {
      return designTokens.semantic.primarySoft;
    }
    if (entry.work_category === 'non_productive') {
      return designTokens.semantic.warningSoft;
    }
    if (entry.is_billable) {
      return designTokens.semantic.successSoft;
    }
    return undefined;
  };

  return (
    <Box>
      <Typography variant="sectionTitle" sx={{ mb: 1.5 }}>
        Entries for {monthLabel}
      </Typography>

      {!entries.length ? (
        <EmptyState
          title="No timesheet entries"
          description="Use the form above to add your first entry, or duplicate a previous day."
        />
      ) : (
        <OperationalDataTable
          maxHeight={520}
          head={
            <TableRow>
              <StickyHeaderCell pinned>
                <TableSortLabel
                  active={sortKey === 'entry_date'}
                  direction={sortKey === 'entry_date' ? sortDirection : 'asc'}
                  onClick={() => handleSort('entry_date')}
                >
                  Date
                </TableSortLabel>
              </StickyHeaderCell>
              {showUser ? <StickyHeaderCell>Designer</StickyHeaderCell> : null}
              <StickyHeaderCell pinned={!showUser}>
                <TableSortLabel
                  active={sortKey === 'tool'}
                  direction={sortKey === 'tool' ? sortDirection : 'asc'}
                  onClick={() => handleSort('tool')}
                >
                  Tool / NP Code
                </TableSortLabel>
              </StickyHeaderCell>
              <StickyHeaderCell>Description</StickyHeaderCell>
              <StickyHeaderCell>Task</StickyHeaderCell>
              <StickyHeaderCell align="right">
                <TableSortLabel
                  active={sortKey === 'hours'}
                  direction={sortKey === 'hours' ? sortDirection : 'asc'}
                  onClick={() => handleSort('hours')}
                >
                  Hours
                </TableSortLabel>
              </StickyHeaderCell>
              <StickyHeaderCell>Category</StickyHeaderCell>
              <StickyHeaderCell>Notes</StickyHeaderCell>
              <StickyHeaderCell>Status</StickyHeaderCell>
              <StickyHeaderCell align="right">Actions</StickyHeaderCell>
            </TableRow>
          }
        >
          {sortedEntries.map((entry) => {
            const editable = !readOnly && isEntryEditable(entry);
            const dayTotal = dailyTotals.get(entry.entry_date) ?? 0;
            const showDayTotal = (dailySubtotals.get(entry.entry_date) ?? 0) > 1;
            const dayOverLimit = dayTotal > dailyLimit;
            const sheet = timesheetById.get(entry.timesheet_id);
            const categoryBg = rowCategoryBg(entry);

            return (
              <ClickableTableRow
                key={entry.id}
                selected={selectedEntryId === entry.id}
                onClick={() => onSelect(selectedEntryId === entry.id ? null : entry)}
              >
                <StickyTableCell
                  pinned
                  sx={{
                    whiteSpace: 'nowrap',
                    bgcolor: categoryBg ?? 'inherit',
                    ...(dayOverLimit ? { borderLeft: `3px solid ${designTokens.semantic.warning}` } : {}),
                  }}
                >
                  {formatDate(entry.entry_date)}
                  {showDayTotal ? (
                    <Typography
                      variant="caption"
                      color={dayOverLimit ? 'warning.main' : 'text.secondary'}
                      sx={{ display: 'block' }}
                    >
                      Day: {formatNumber(dayTotal, 1)}h
                    </Typography>
                  ) : null}
                </StickyTableCell>
                {showUser ? (
                  <StickyTableCell sx={{ whiteSpace: 'nowrap', bgcolor: categoryBg ?? 'inherit' }}>
                    {formatCellValue(entry.user_name) || '—'}
                  </StickyTableCell>
                ) : null}
                <StickyTableCell pinned={!showUser} sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  <TimesheetToolCell entry={entry} />
                </StickyTableCell>
                <StickyTableCell sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  {entryDescription(entry)}
                </StickyTableCell>
                <StickyTableCell sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  {entryTaskLabel(entry)}
                </StickyTableCell>
                <StickyTableCell align="right" sx={{ fontWeight: 700, bgcolor: categoryBg ?? 'inherit' }}>
                  {formatNumber(entry.hours, 1)}
                </StickyTableCell>
                <StickyTableCell sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  <TimesheetWorkCategoryBadge entry={entry} />
                </StickyTableCell>
                <StickyTableCell sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  {formatCellValue(entry.description) || '—'}
                </StickyTableCell>
                <StickyTableCell sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  <TimesheetStatusChip status={sheet?.status ?? 'draft'} />
                </StickyTableCell>
                <StickyTableCell align="right" sx={{ bgcolor: categoryBg ?? 'inherit' }}>
                  {editable ? (
                    <Box sx={{ display: 'inline-flex', gap: 0.25 }}>
                      <Tooltip title="Edit">
                        <IconButton
                          size="small"
                          onClick={(event) => {
                            event.stopPropagation();
                            onEdit(entry);
                          }}
                        >
                          <EditRoundedIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      {onDuplicate ? (
                        <Tooltip title="Duplicate row">
                          <IconButton
                            size="small"
                            onClick={(event) => {
                              event.stopPropagation();
                              onDuplicate(entry);
                            }}
                          >
                            <ContentCopyRoundedIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      ) : null}
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          color="error"
                          disabled={deletingId === entry.id}
                          onClick={(event) => {
                            event.stopPropagation();
                            onDelete(entry);
                          }}
                        >
                          <DeleteOutlineRoundedIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  ) : (
                    '—'
                  )}
                </StickyTableCell>
              </ClickableTableRow>
            );
          })}
        </OperationalDataTable>
      )}
    </Box>
  );
}
