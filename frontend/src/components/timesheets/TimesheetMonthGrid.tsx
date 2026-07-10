import { memo, useCallback, useMemo, useRef, type KeyboardEvent } from 'react';
import {
  Checkbox,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import type { TaskType, TimesheetEntry } from '../../types';
import type { TimesheetProjectLookup } from '../../types/TimesheetEntry';
import { taskTypesForProjectStream } from '../../utils/timesheetTaskTypes';
import {
  dayName,
  GRID_COLUMNS,
  isWeekend,
  nextGridCell,
  parseClipboardRows,
} from '../../utils/timesheetMonth';
import { formatDisplayValue, formatNumber } from '../../utils/format';

export interface TimesheetGridRow {
  clientId: string;
  entryId?: string;
  timesheetId?: string;
  entryDate: string;
  projectId: string | null;
  toolNumber: string;
  customerName: string;
  taskTypeId: string | null;
  workCategory: 'productive' | 'non_productive';
  npCodeId: string | null;
  isBillable: boolean;
  hours: string;
  notes: string;
  isDirty: boolean;
  isHoliday: boolean;
  isReadOnly: boolean;
}

interface TimesheetMonthGridProps {
  rows: TimesheetGridRow[];
  projects: TimesheetProjectLookup[];
  taskTypes: TaskType[];
  holidayDates: Set<string>;
  readOnly: boolean;
  onRowsChange: (rows: TimesheetGridRow[]) => void;
  onSaveRow: (row: TimesheetGridRow) => Promise<void>;
}

const COLUMN_LABELS: Record<(typeof GRID_COLUMNS)[number], string> = {
  entryDate: 'Date',
  day: 'Day',
  toolNumber: 'Tool Number',
  customer: 'Customer',
  task: 'Task',
  billable: 'Billable',
  hours: 'Hours',
  notes: 'Notes',
};

function rowBackground(row: TimesheetGridRow): string | undefined {
  if (row.isHoliday || isWeekend(row.entryDate)) return 'action.hover';
  if (row.isDirty) return 'warning.50';
  return undefined;
}

function TimesheetMonthGridComponent({
  rows,
  projects,
  taskTypes,
  holidayDates,
  readOnly,
  onRowsChange,
  onSaveRow,
}: TimesheetMonthGridProps) {
  const cellRefs = useRef<Map<string, HTMLInputElement | HTMLSelectElement>>(new Map());

  const projectByTool = useMemo(() => {
    const map = new Map<string, TimesheetProjectLookup>();
    for (const project of projects) {
      map.set(project.tool_number.trim().toLowerCase(), project);
    }
    return map;
  }, [projects]);

  const updateRow = useCallback(
    (clientId: string, patch: Partial<TimesheetGridRow>) => {
      onRowsChange(
        rows.map((row) =>
          row.clientId === clientId ? { ...row, ...patch, isDirty: true } : row,
        ),
      );
    },
    [onRowsChange, rows],
  );

  const applyProjectTool = useCallback(
    (row: TimesheetGridRow, toolNumber: string) => {
      const project = projectByTool.get(toolNumber.trim().toLowerCase());
      if (!project) {
        updateRow(row.clientId, { toolNumber, projectId: null, customerName: '' });
        return;
      }
      updateRow(row.clientId, {
        toolNumber: project.tool_number,
        projectId: project.id,
        customerName: project.customer_name ?? '',
        workCategory: 'productive',
        npCodeId: null,
      });
    },
    [projectByTool, updateRow],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent, rowIndex: number, columnIndex: number) => {
      if (event.key === 'Tab' || event.key === 'Enter') {
        event.preventDefault();
        const next = nextGridCell(rowIndex, columnIndex, rows.length);
        const key = `${next.row}-${GRID_COLUMNS[next.col]}`;
        cellRefs.current.get(key)?.focus();
        return;
      }

      let nextRow = rowIndex;
      let nextCol = columnIndex;
      if (event.key === 'ArrowDown') nextRow = Math.min(rows.length - 1, rowIndex + 1);
      else if (event.key === 'ArrowUp') nextRow = Math.max(0, rowIndex - 1);
      else if (event.key === 'ArrowRight') nextCol = Math.min(GRID_COLUMNS.length - 1, columnIndex + 1);
      else if (event.key === 'ArrowLeft') nextCol = Math.max(0, columnIndex - 1);
      else return;

      event.preventDefault();
      const key = `${nextRow}-${GRID_COLUMNS[nextCol]}`;
      cellRefs.current.get(key)?.focus();
    },
    [rows.length],
  );

  const handlePaste = useCallback(
    (event: React.ClipboardEvent, startRowIndex: number) => {
      if (readOnly) return;
      const parsed = parseClipboardRows(event.clipboardData.getData('text'));
      if (!parsed.length) return;
      event.preventDefault();
      const nextRows = [...rows];
      parsed.forEach((cells, offset) => {
        const index = startRowIndex + offset;
        if (index >= nextRows.length) {
          nextRows.push(createBlankRow(cells[0] || nextRows[nextRows.length - 1]?.entryDate || ''));
        }
        const row = nextRows[index];
        if (row.isReadOnly) return;
        const toolNumber = cells[2] ?? cells[0] ?? row.toolNumber;
        const project = projectByTool.get(toolNumber.trim().toLowerCase());
        nextRows[index] = {
          ...row,
          entryDate: cells[0] || row.entryDate,
          toolNumber: project?.tool_number ?? toolNumber,
          projectId: project?.id ?? row.projectId,
          customerName: project?.customer_name ?? cells[3] ?? row.customerName,
          hours: cells[6] ?? cells[1] ?? row.hours,
          notes: cells[7] ?? cells[5] ?? row.notes,
          isDirty: true,
        };
      });
      onRowsChange(nextRows);
    },
    [onRowsChange, projectByTool, readOnly, rows],
  );

  const saveRow = useCallback(
    async (row: TimesheetGridRow) => {
      if (readOnly || row.isReadOnly || !row.isDirty) return;
      await onSaveRow(row);
    },
    [onSaveRow, readOnly],
  );

  return (
    <TableContainer component={Paper} sx={{ borderRadius: 2, border: 1, borderColor: 'divider' }}>
      <Table size="small" stickyHeader sx={{ minWidth: 1100 }}>
        <TableHead>
          <TableRow>
            {GRID_COLUMNS.map((column) => (
              <TableCell key={column} sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
                {COLUMN_LABELS[column]}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody onPaste={(event) => handlePaste(event, 0)}>
          {rows.map((row, rowIndex) => {
            const weekend = isWeekend(row.entryDate);
            const holiday = holidayDates.has(row.entryDate);
            const disabled = readOnly || row.isReadOnly || weekend || holiday;
            return (
              <TableRow
                key={row.clientId}
                hover={!disabled}
                sx={{ bgcolor: rowBackground({ ...row, isHoliday: holiday }) }}
              >
                <TableCell sx={{ width: 120 }}>
                  <TextField
                    size="small"
                    type="date"
                    value={row.entryDate}
                    disabled={disabled}
                    inputRef={(node) => {
                      if (node) cellRefs.current.set(`${rowIndex}-entryDate`, node);
                    }}
                    onChange={(event) =>
                      updateRow(row.clientId, { entryDate: event.target.value })
                    }
                    onBlur={() => void saveRow(row)}
                    onKeyDown={(event) => handleKeyDown(event, rowIndex, 0)}
                    slotProps={{ input: { sx: { fontSize: 13 } } }}
                  />
                </TableCell>
                <TableCell sx={{ width: 56, color: 'text.secondary' }}>
                  {dayName(row.entryDate)}
                </TableCell>
                <TableCell sx={{ minWidth: 130 }}>
                  <TextField
                    size="small"
                    value={row.toolNumber}
                    disabled={disabled}
                    placeholder="Tool No."
                    inputRef={(node) => {
                      if (node) cellRefs.current.set(`${rowIndex}-toolNumber`, node);
                    }}
                    onChange={(event) => applyProjectTool(row, event.target.value)}
                    onBlur={() => void saveRow(row)}
                    onKeyDown={(event) => handleKeyDown(event, rowIndex, 2)}
                    slotProps={{ input: { sx: { fontSize: 13 } } }}
                  />
                </TableCell>
                <TableCell sx={{ minWidth: 140 }}>
                  <Typography variant="body2">{formatDisplayValue(row.customerName)}</Typography>
                </TableCell>
                <TableCell sx={{ minWidth: 160 }}>
                  <TextField
                    select
                    size="small"
                    fullWidth
                    value={row.taskTypeId ?? ''}
                    disabled={disabled || !row.projectId}
                    onChange={(event) =>
                      updateRow(row.clientId, { taskTypeId: event.target.value || null })
                    }
                    onBlur={() => void saveRow(row)}
                    slotProps={{ input: { sx: { fontSize: 13 } } }}
                  >
                    <MenuItem value="">Select task</MenuItem>
                    {taskTypesForProjectStream(
                      taskTypes,
                      projects.find((project) => project.id === row.projectId)?.stream_id,
                    ).map((task) => (
                        <MenuItem key={task.id} value={task.id}>
                          {task.name}
                        </MenuItem>
                      ))}
                  </TextField>
                </TableCell>
                <TableCell align="center" sx={{ width: 72 }}>
                  <Checkbox
                    size="small"
                    checked={row.isBillable}
                    disabled={disabled}
                    onChange={(event) =>
                      updateRow(row.clientId, { isBillable: event.target.checked })
                    }
                  />
                </TableCell>
                <TableCell sx={{ width: 88 }}>
                  <TextField
                    size="small"
                    value={row.hours}
                    disabled={disabled}
                    inputRef={(node) => {
                      if (node) cellRefs.current.set(`${rowIndex}-hours`, node);
                    }}
                    onChange={(event) => updateRow(row.clientId, { hours: event.target.value })}
                    onBlur={() => void saveRow(row)}
                    onKeyDown={(event) => handleKeyDown(event, rowIndex, 6)}
                    slotProps={{ input: { sx: { fontSize: 13 } } }}
                  />
                </TableCell>
                <TableCell sx={{ minWidth: 180 }}>
                  <TextField
                    size="small"
                    fullWidth
                    value={row.notes}
                    disabled={disabled}
                    onChange={(event) => updateRow(row.clientId, { notes: event.target.value })}
                    onBlur={() => void saveRow(row)}
                    slotProps={{ input: { sx: { fontSize: 13 } } }}
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

export function entryToGridRow(entry: TimesheetEntry, readOnly: boolean): TimesheetGridRow {
  return {
    clientId: entry.id,
    entryId: entry.id,
    timesheetId: entry.timesheet_id,
    entryDate: entry.entry_date,
    projectId: entry.project_id,
    toolNumber: entry.project_tool_number ?? '',
    customerName: entry.customer_name ?? '',
    taskTypeId: entry.task_type_id,
    workCategory: entry.work_category,
    npCodeId: entry.non_productive_code_id,
    isBillable: entry.is_billable,
    hours: String(entry.hours),
    notes: entry.description ?? '',
    isDirty: false,
    isHoliday: false,
    isReadOnly: readOnly,
  };
}

export function createBlankRow(entryDate: string): TimesheetGridRow {
  return {
    clientId: `new-${entryDate}-${Math.random().toString(36).slice(2, 8)}`,
    entryDate,
    projectId: null,
    toolNumber: '',
    customerName: '',
    taskTypeId: null,
    workCategory: 'productive',
    npCodeId: null,
    isBillable: true,
    hours: '',
    notes: '',
    isDirty: false,
    isHoliday: false,
    isReadOnly: false,
  };
}

export function buildMonthGridRows(
  days: string[],
  entries: TimesheetEntry[],
  readOnly: boolean,
  holidayDates: Set<string>,
): TimesheetGridRow[] {
  const entriesByDate = new Map<string, TimesheetEntry[]>();
  for (const entry of entries) {
    const list = entriesByDate.get(entry.entry_date) ?? [];
    list.push(entry);
    entriesByDate.set(entry.entry_date, list);
  }

  const rows: TimesheetGridRow[] = [];
  for (const day of days) {
    const dayEntries = entriesByDate.get(day);
    if (dayEntries?.length) {
      for (const entry of dayEntries) {
        rows.push({
          ...entryToGridRow(entry, readOnly),
          isHoliday: holidayDates.has(day),
        });
      }
      continue;
    }
    rows.push({
      ...createBlankRow(day),
      isHoliday: holidayDates.has(day),
    });
  }
  return rows;
}

export function summarizeDailyHours(rows: TimesheetGridRow[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const row of rows) {
    const parsed = Number(row.hours);
    if (!Number.isFinite(parsed) || parsed <= 0) continue;
    totals.set(row.entryDate, (totals.get(row.entryDate) ?? 0) + parsed);
  }
  return totals;
}

export const TimesheetMonthGrid = memo(TimesheetMonthGridComponent);

export function summarizeHours(rows: TimesheetGridRow[]): number {
  return rows.reduce((total, row) => {
    const parsed = Number(row.hours);
    return Number.isFinite(parsed) ? total + parsed : total;
  }, 0);
}

export function formatHoursTotal(value: number): string {
  return formatNumber(value, 1);
}
