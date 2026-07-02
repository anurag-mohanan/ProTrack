export function weekStartMonday(value: string | Date): string {
  const copy = new Date(typeof value === 'string' ? `${value}T12:00:00` : value);
  const day = copy.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  copy.setDate(copy.getDate() + diff);
  return copy.toISOString().slice(0, 10);
}

export function monthBounds(monthValue: string): { start: string; end: string; days: string[] } {
  const [year, month] = monthValue.split('-').map(Number);
  const startDate = new Date(year, month - 1, 1);
  const endDate = new Date(year, month, 0);
  const days: string[] = [];
  for (let day = 1; day <= endDate.getDate(); day += 1) {
    const iso = new Date(year, month - 1, day).toISOString().slice(0, 10);
    days.push(iso);
  }
  return {
    start: startDate.toISOString().slice(0, 10),
    end: endDate.toISOString().slice(0, 10),
    days,
  };
}

export function dayName(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' });
}

export function isWeekend(isoDate: string): boolean {
  const day = new Date(`${isoDate}T12:00:00`).getDay();
  return day === 0 || day === 6;
}

export function countWorkingDays(
  days: string[],
  holidayDates: Set<string>,
): number {
  return days.filter((day) => !isWeekend(day) && !holidayDates.has(day)).length;
}

export function formatMonthLabel(monthValue: string): string {
  const [year, month] = monthValue.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  });
}

export const GRID_COLUMNS = [
  'entryDate',
  'day',
  'toolNumber',
  'customer',
  'task',
  'billable',
  'hours',
  'notes',
] as const;

export type GridColumnKey = (typeof GRID_COLUMNS)[number];

export function nextGridCell(
  rowIndex: number,
  columnIndex: number,
  rowCount: number,
): { row: number; col: number } {
  const col = columnIndex + 1;
  if (col >= GRID_COLUMNS.length) {
    return { row: Math.min(rowIndex + 1, rowCount - 1), col: 2 };
  }
  return { row: rowIndex, col };
}

export function parseClipboardRows(text: string): string[][] {
  return text
    .trim()
    .split(/\r?\n/)
    .map((line) => line.split('\t').map((cell) => cell.trim()));
}
