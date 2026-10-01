import { Stack } from '@mui/material';
import { FormField, FormSelect } from '../../ui/design-system';
import type { Shift } from '../../../types/ResourceShifts';
import { WINDOW_MODE_OPTIONS, type AllocationWindowState, type WindowMode } from './allocationWindow';

type Props = {
  value: AllocationWindowState;
  onChange: (next: AllocationWindowState) => void;
  shifts: Shift[];
  showDates?: boolean;
  allModeLabel?: string;
  modes?: WindowMode[];
};

export function AllocationWindowFields({ value, onChange, shifts, showDates = true, allModeLabel, modes }: Props) {
  const set = (patch: Partial<AllocationWindowState>) => onChange({ ...value, ...patch });
  const modeOptions = WINDOW_MODE_OPTIONS.filter((o) => !modes || modes.includes(o.value)).map((o) =>
    o.value === 'all' && allModeLabel ? { ...o, label: allModeLabel } : o,
  );
  return (
    <Stack spacing={1.5}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
        <FormSelect
          label="Usage window"
          value={value.mode}
          onChange={(event) => set({ mode: String(event.target.value) as WindowMode })}
          options={modeOptions}
          sx={{ minWidth: 200 }}
        />
        {value.mode === 'shift' ? (
          <FormSelect
            label="Shift"
            required
            value={value.shiftId}
            onChange={(event) => set({ shiftId: String(event.target.value) })}
            options={shifts.map((s) => ({
              value: s.id,
              label: `${s.name} (${s.start_time}–${s.end_time})`,
            }))}
            sx={{ flex: 1 }}
          />
        ) : null}
        {value.mode === 'custom' ? (
          <>
            <FormField
              label="Start time"
              type="time"
              required
              value={value.startTime}
              onChange={(event) => set({ startTime: event.target.value })}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormField
              label="End time"
              type="time"
              required
              value={value.endTime}
              onChange={(event) => set({ endTime: event.target.value })}
              helper="Overnight allowed, e.g. 22:00–06:00"
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </>
        ) : null}
      </Stack>
      {showDates ? (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <FormField
            label="Start date"
            type="date"
            value={value.startDate}
            onChange={(event) => set({ startDate: event.target.value })}
            helper="Defaults to today"
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <FormField
            label="End date (optional)"
            type="date"
            value={value.endDate}
            onChange={(event) => set({ endDate: event.target.value })}
            helper="Leave empty for open-ended"
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Stack>
      ) : null}
    </Stack>
  );
}
