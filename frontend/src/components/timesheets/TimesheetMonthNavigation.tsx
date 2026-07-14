import { IconButton, Stack, TextField, Typography } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import type { ReactNode } from 'react';
import { formatMonthLabel, shiftMonth } from '../../utils/timesheetMonth';

interface TimesheetMonthNavigationProps {
  monthValue: string;
  onMonthChange: (monthValue: string) => void;
  /** Optional trailing controls (mode tabs, Submit) — keeps one compact toolbar. */
  endAdornment?: ReactNode;
}

/**
 * Compact month toolbar: prev/next + label + single jump picker.
 * Month/Year/Jump triplicate controls were removed — same job three times.
 */
export function TimesheetMonthNavigation({
  monthValue,
  onMonthChange,
  endAdornment,
}: TimesheetMonthNavigationProps) {
  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={1.25}
      sx={{
        mb: 1.5,
        alignItems: { xs: 'stretch', sm: 'center' },
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 1,
      }}
    >
      <Stack
        direction="row"
        spacing={0.5}
        sx={{ alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}
      >
        <IconButton
          size="small"
          aria-label="Previous month"
          onClick={() => onMonthChange(shiftMonth(monthValue, -1))}
        >
          <ChevronLeftIcon />
        </IconButton>
        <Typography
          sx={{
            minWidth: 132,
            textAlign: 'center',
            fontWeight: 800,
            fontSize: '1.05rem',
            letterSpacing: '-0.01em',
          }}
        >
          {formatMonthLabel(monthValue)}
        </Typography>
        <IconButton
          size="small"
          aria-label="Next month"
          onClick={() => onMonthChange(shiftMonth(monthValue, 1))}
        >
          <ChevronRightIcon />
        </IconButton>
        <TextField
          type="month"
          size="small"
          label="Jump"
          value={monthValue}
          onChange={(event) => onMonthChange(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{
            ml: { xs: 0, sm: 1 },
            minWidth: 148,
            maxWidth: 168,
            '& .MuiOutlinedInput-root': { borderRadius: 2 },
          }}
        />
      </Stack>

      {endAdornment ? (
        <Stack
          direction="row"
          spacing={1}
          sx={{ alignItems: 'center', flexWrap: 'wrap', justifyContent: { xs: 'flex-start', sm: 'flex-end' } }}
        >
          {endAdornment}
        </Stack>
      ) : null}
    </Stack>
  );
}
