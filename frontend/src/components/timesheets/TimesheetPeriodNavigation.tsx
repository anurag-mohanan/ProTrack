import { IconButton, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography, MenuItem } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import type { ReactNode } from 'react';
import { ReportPeriodSelectors } from '../reports/ReportPeriodSelectors';
import {
  shiftPeriodAnchor,
  TIMESHEET_PERIOD_OPTIONS,
  type ReportPeriodType,
} from '../../utils/reportPeriodSelection';

interface TimesheetPeriodNavigationProps {
  periodType: ReportPeriodType;
  anchor: string;
  periodLabel: string;
  onPeriodTypeChange: (periodType: ReportPeriodType) => void;
  onAnchorChange: (anchor: string) => void;
  /** Optional trailing controls (mode tabs, Submit). */
  endAdornment?: ReactNode;
  /** Extra row under the period controls (e.g. By designer / By team). */
  secondaryAdornment?: ReactNode;
}

/**
 * Week / month / quarter / year toolbar for the All Users timesheet overview.
 */
export function TimesheetPeriodNavigation({
  periodType,
  anchor,
  periodLabel,
  onPeriodTypeChange,
  onAnchorChange,
  endAdornment,
  secondaryAdornment,
}: TimesheetPeriodNavigationProps) {
  return (
    <Stack spacing={1.25} sx={{ mb: 1.5 }}>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1.25}
        sx={{
          alignItems: { xs: 'stretch', md: 'center' },
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Stack
          direction="row"
          spacing={0.75}
          sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0, gap: 0.75 }}
        >
          <TextField
            select
            size="small"
            label="Period"
            value={periodType}
            onChange={(event) => onPeriodTypeChange(event.target.value as ReportPeriodType)}
            sx={{ minWidth: 120 }}
          >
            {TIMESHEET_PERIOD_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </TextField>
          <ReportPeriodSelectors
            periodType={periodType}
            anchor={anchor}
            onAnchorChange={onAnchorChange}
            minWidth={140}
          />
          <IconButton
            size="small"
            aria-label="Previous period"
            onClick={() => onAnchorChange(shiftPeriodAnchor(periodType, anchor, -1))}
          >
            <ChevronLeftIcon />
          </IconButton>
          <Typography
            sx={{
              minWidth: { xs: 0, sm: 200 },
              textAlign: 'center',
              fontWeight: 700,
              fontSize: '0.95rem',
            }}
          >
            {periodLabel}
          </Typography>
          <IconButton
            size="small"
            aria-label="Next period"
            onClick={() => onAnchorChange(shiftPeriodAnchor(periodType, anchor, 1))}
          >
            <ChevronRightIcon />
          </IconButton>
        </Stack>

        {endAdornment ? (
          <Stack
            direction="row"
            spacing={1}
            sx={{
              alignItems: 'center',
              flexWrap: 'wrap',
              justifyContent: { xs: 'flex-start', md: 'flex-end' },
            }}
          >
            {endAdornment}
          </Stack>
        ) : null}
      </Stack>

      {secondaryAdornment}
    </Stack>
  );
}

interface OverviewGroupingToggleProps {
  value: 'designer' | 'team';
  onChange: (value: 'designer' | 'team') => void;
}

export function OverviewGroupingToggle({ value, onChange }: OverviewGroupingToggleProps) {
  return (
    <ToggleButtonGroup
      size="small"
      exclusive
      value={value}
      onChange={(_, next) => {
        if (next) onChange(next);
      }}
    >
      <ToggleButton value="designer">By designer (full hours)</ToggleButton>
      <ToggleButton value="team">By team (membership dates)</ToggleButton>
    </ToggleButtonGroup>
  );
}
