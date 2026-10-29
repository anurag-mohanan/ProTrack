import { MenuItem, TextField } from '@mui/material';
import type { PerformancePeriodType } from '../../types/EngineeringPerformance';
import { ReportPeriodSelectors } from './ReportPeriodSelectors';
import { PERIOD_OPTIONS, fyLabel, fyQuarterLabel } from './reportFormat';
import type { PerformancePeriodState } from './usePerformancePeriod';

interface PerformancePeriodFieldsProps {
  period: PerformancePeriodState;
  label?: string;
  disabled?: boolean;
}

/** Period inputs rendered as grid cells; place inside the caller's filter grid. */
export function PerformancePeriodFields({ period, label = 'Period', disabled = false }: PerformancePeriodFieldsProps) {
  const { periodType, fyStartMonth } = period;
  return (
    <>
      <TextField
        select
        size="small"
        label={label}
        value={periodType}
        onChange={(event) => period.changePeriodType(event.target.value as PerformancePeriodType)}
        disabled={disabled}
        fullWidth
      >
        {PERIOD_OPTIONS.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
      {periodType === 'weekly' || periodType === 'monthly' ? (
        <ReportPeriodSelectors
          periodType={periodType}
          anchor={period.anchor}
          onAnchorChange={period.setAnchor}
          fluid
        />
      ) : null}
      {periodType === 'quarterly' || periodType === 'yearly' ? (
        <TextField
          select
          size="small"
          label="Financial year"
          value={period.selectedFyYear}
          onChange={(event) => period.setFyYear(Number(event.target.value))}
          disabled={disabled}
          fullWidth
        >
          {period.fyYears.map((year) => (
            <MenuItem key={year} value={year}>
              {fyLabel(year, fyStartMonth)}
            </MenuItem>
          ))}
        </TextField>
      ) : null}
      {periodType === 'quarterly' ? (
        <TextField
          select
          size="small"
          label="Quarter"
          value={period.selectedFyQuarter}
          onChange={(event) => period.setFyQuarter(Number(event.target.value))}
          disabled={disabled}
          fullWidth
        >
          {[1, 2, 3, 4].map((quarter) => (
            <MenuItem key={quarter} value={quarter}>
              {fyQuarterLabel(quarter, fyStartMonth)}
            </MenuItem>
          ))}
        </TextField>
      ) : null}
      {periodType === 'custom' ? (
        <>
          <TextField
            size="small"
            type="date"
            label="From"
            value={period.customStart}
            onChange={(event) => period.setCustomStart(event.target.value)}
            disabled={disabled}
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
          />
          <TextField
            size="small"
            type="date"
            label="To"
            value={period.customEnd}
            onChange={(event) => period.setCustomEnd(event.target.value)}
            error={Boolean(period.customStart && period.customEnd && period.customEnd < period.customStart)}
            helperText={period.customRangeError ?? ' '}
            disabled={disabled}
            slotProps={{ inputLabel: { shrink: true } }}
            fullWidth
          />
        </>
      ) : null}
    </>
  );
}
