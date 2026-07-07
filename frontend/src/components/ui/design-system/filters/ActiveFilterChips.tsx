import { Chip, Stack } from '@mui/material';

export interface ActiveFilterChip {
  key: string;
  label: string;
  onRemove: () => void;
}

interface ActiveFilterChipsProps {
  chips: ActiveFilterChip[];
  onClearAll?: () => void;
}

export function ActiveFilterChips({ chips, onClearAll }: ActiveFilterChipsProps) {
  if (!chips.length) return null;

  return (
    <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', rowGap: 0.75 }}>
      {chips.map((chip) => (
        <Chip
          key={chip.key}
          label={chip.label}
          onDelete={chip.onRemove}
          size="small"
          variant="outlined"
          sx={{ height: 26, fontSize: '0.75rem' }}
        />
      ))}
      {onClearAll ? (
        <Chip
          label="Clear all"
          size="small"
          color="primary"
          onClick={onClearAll}
          variant="filled"
          sx={{ height: 26, fontSize: '0.75rem' }}
        />
      ) : null}
    </Stack>
  );
}
