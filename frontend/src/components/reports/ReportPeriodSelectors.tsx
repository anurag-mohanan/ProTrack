import { MenuItem, TextField } from '@mui/material';
import {
  availableYears,
  defaultAnchorForPeriod,
  firstDayOfMonth,
  firstDayOfQuarter,
  firstDayOfYear,
  monthOptions,
  normalizeAnchor,
  quarterOptions,
  selectionFromAnchor,
  toIsoDate,
  weeksInMonth,
  type ReportPeriodType,
} from '../../utils/reportPeriodSelection';

interface ReportPeriodSelectorsProps {
  periodType: ReportPeriodType;
  anchor: string;
  onAnchorChange: (anchor: string) => void;
  /** Optional min width for each field (ignored when fluid). */
  minWidth?: number;
  /** Stretch fields to fill parent grid/flex cells without forcing overflow. */
  fluid?: boolean;
}

function recentYearMonthOptions(count = 24): { value: string; label: string; year: number; month: number }[] {
  const options: { value: string; label: string; year: number; month: number }[] = [];
  const cursor = new Date();
  cursor.setDate(1);
  for (let i = 0; i < count; i += 1) {
    const year = cursor.getFullYear();
    const month = cursor.getMonth() + 1;
    const monthLabel = monthOptions().find((row) => row.value === month)?.label ?? String(month);
    options.push({
      value: `${year}-${String(month).padStart(2, '0')}`,
      label: `${monthLabel} ${year}`,
      year,
      month,
    });
    cursor.setMonth(cursor.getMonth() - 1);
  }
  return options;
}

/**
 * Period-aware selectors that replace a raw anchor date picker:
 * - Weekly → Month + Week
 * - Monthly → Year + Month
 * - Quarterly → Year + Quarter
 * - Yearly → Year
 */
export function ReportPeriodSelectors({
  periodType,
  anchor,
  onAnchorChange,
  minWidth = 150,
  fluid = false,
}: ReportPeriodSelectorsProps) {
  const fieldSx = fluid
    ? { width: '100%', minWidth: 0, maxWidth: '100%' }
    : { minWidth };
  const yearFieldSx = fluid
    ? fieldSx
    : { minWidth: Math.min(minWidth, 110) };
  const weekFieldSx = fluid
    ? fieldSx
    : { minWidth: Math.max(minWidth, 230) };
  const monthComboSx = fluid
    ? fieldSx
    : { minWidth: Math.max(minWidth, 160) };
  const selection = selectionFromAnchor(periodType, anchor || defaultAnchorForPeriod(periodType));
  const years = availableYears();
  const weeks = weeksInMonth(selection.year, selection.month);
  const activeWeek =
    weeks.find((week) => week.monday === selection.weekMonday)?.monday ??
    weeks[0]?.monday ??
    selection.weekMonday;
  const yearMonthValue = `${selection.year}-${String(selection.month).padStart(2, '0')}`;
  const yearMonthOptions = recentYearMonthOptions();
  if (!yearMonthOptions.some((row) => row.value === yearMonthValue)) {
    const monthLabel =
      monthOptions().find((row) => row.value === selection.month)?.label ?? String(selection.month);
    yearMonthOptions.unshift({
      value: yearMonthValue,
      label: `${monthLabel} ${selection.year}`,
      year: selection.year,
      month: selection.month,
    });
  }

  if (periodType === 'weekly') {
    return (
      <>
        <TextField
          select
          size="small"
          label="Month"
          value={yearMonthValue}
          onChange={(event) => {
            const [yearText, monthText] = event.target.value.split('-');
            const year = Number(yearText);
            const month = Number(monthText);
            const nextWeeks = weeksInMonth(year, month);
            const monday = nextWeeks[0]?.monday ?? firstDayOfMonth(year, month);
            onAnchorChange(normalizeAnchor('weekly', monday));
          }}
          sx={monthComboSx}
        >
          {yearMonthOptions.map((row) => (
            <MenuItem key={row.value} value={row.value}>
              {row.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Week"
          value={activeWeek}
          onChange={(event) => onAnchorChange(normalizeAnchor('weekly', event.target.value))}
          sx={weekFieldSx}
          helperText="Mon–Sun week"
        >
          {weeks.map((week) => (
            <MenuItem key={week.monday} value={week.monday}>
              {week.label}
            </MenuItem>
          ))}
        </TextField>
      </>
    );
  }

  if (periodType === 'monthly') {
    return (
      <>
        <TextField
          select
          size="small"
          label="Year"
          value={selection.year}
          onChange={(event) => {
            const year = Number(event.target.value);
            onAnchorChange(firstDayOfMonth(year, selection.month));
          }}
          sx={yearFieldSx}
        >
          {years.map((year) => (
            <MenuItem key={year} value={year}>
              {year}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Month"
          value={selection.month}
          onChange={(event) => {
            const month = Number(event.target.value);
            onAnchorChange(firstDayOfMonth(selection.year, month));
          }}
          sx={fieldSx}
        >
          {monthOptions().map((month) => (
            <MenuItem key={month.value} value={month.value}>
              {month.label}
            </MenuItem>
          ))}
        </TextField>
      </>
    );
  }

  if (periodType === 'quarterly') {
    return (
      <>
        <TextField
          select
          size="small"
          label="Year"
          value={selection.year}
          onChange={(event) => {
            const year = Number(event.target.value);
            onAnchorChange(firstDayOfQuarter(year, selection.quarter));
          }}
          sx={yearFieldSx}
        >
          {years.map((year) => (
            <MenuItem key={year} value={year}>
              {year}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Quarter"
          value={selection.quarter}
          onChange={(event) => {
            const quarter = Number(event.target.value);
            onAnchorChange(firstDayOfQuarter(selection.year, quarter));
          }}
          sx={fieldSx}
        >
          {quarterOptions().map((quarter) => (
            <MenuItem key={quarter.value} value={quarter.value}>
              {quarter.label}
            </MenuItem>
          ))}
        </TextField>
      </>
    );
  }

  if (periodType === 'yearly') {
    return (
      <TextField
        select
        size="small"
        label="Year"
        value={selection.year}
        onChange={(event) => onAnchorChange(firstDayOfYear(Number(event.target.value)))}
        sx={yearFieldSx}
      >
        {years.map((year) => (
          <MenuItem key={year} value={year}>
            {year}
          </MenuItem>
        ))}
      </TextField>
    );
  }

  return (
    <TextField
      size="small"
      type="date"
      label="Anchor date"
      value={anchor}
      onChange={(event) => onAnchorChange(event.target.value)}
      slotProps={{ inputLabel: { shrink: true } }}
      sx={fieldSx}
    />
  );
}

/** Convenience: ensure stored anchor stays canonical when period type changes. */
export function syncAnchorForPeriodChange(
  periodType: ReportPeriodType,
  currentAnchor: string,
): string {
  return normalizeAnchor(periodType, currentAnchor || toIsoDate(new Date()));
}
