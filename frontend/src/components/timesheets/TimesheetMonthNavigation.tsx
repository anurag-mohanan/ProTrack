import { IconButton, Stack, TextField, Typography } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { formatMonthLabel, shiftMonth } from '../../utils/timesheetMonth';

interface TimesheetMonthNavigationProps {
  monthValue: string;
  onMonthChange: (monthValue: string) => void;
}

export function TimesheetMonthNavigation({
  monthValue,
  onMonthChange,
}: TimesheetMonthNavigationProps) {
  const [year, month] = monthValue.split('-').map(Number);

  return (
    <Stack spacing={1.5} sx={{ mb: 2 }}>
      <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center', justifyContent: 'center' }}>
        <IconButton
          aria-label="Previous month"
          onClick={() => onMonthChange(shiftMonth(monthValue, -1))}
        >
          <ChevronLeftIcon />
        </IconButton>
        <Typography variant="h5" sx={{ minWidth: 160, textAlign: 'center', fontWeight: 700 }}>
          {formatMonthLabel(monthValue)}
        </Typography>
        <IconButton
          aria-label="Next month"
          onClick={() => onMonthChange(shiftMonth(monthValue, 1))}
        >
          <ChevronRightIcon />
        </IconButton>
      </Stack>

      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', justifyContent: { xs: 'center', sm: 'flex-start' } }}>
        <TextField
          select
          size="small"
          label="Month"
          value={month}
          onChange={(event) =>
            onMonthChange(`${year}-${String(Number(event.target.value)).padStart(2, '0')}`)
          }
          slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
          sx={{ minWidth: 130 }}
        >
          {Array.from({ length: 12 }, (_, index) => (
            <option key={index + 1} value={index + 1}>
              {new Date(2000, index, 1).toLocaleDateString(undefined, { month: 'long' })}
            </option>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Year"
          value={year}
          onChange={(event) =>
            onMonthChange(`${Number(event.target.value)}-${String(month).padStart(2, '0')}`)
          }
          slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
          sx={{ minWidth: 100 }}
        >
          {Array.from({ length: 7 }, (_, index) => {
            const optionYear = new Date().getFullYear() - 3 + index;
            return (
              <option key={optionYear} value={optionYear}>
                {optionYear}
              </option>
            );
          })}
        </TextField>
        <TextField
          type="month"
          size="small"
          label="Jump to"
          value={monthValue}
          onChange={(event) => onMonthChange(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 150 }}
        />
      </Stack>
    </Stack>
  );
}
