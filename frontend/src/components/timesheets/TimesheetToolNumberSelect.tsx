import { Autocomplete, Box, TextField, Typography, createFilterOptions } from '@mui/material';
import type { TimesheetToolOption } from './timesheetToolOptions';

interface TimesheetToolNumberSelectProps {
  label?: string;
  value: TimesheetToolOption | null;
  options: TimesheetToolOption[];
  disabled?: boolean;
  onChange: (option: TimesheetToolOption | null) => void;
  onInputChange?: (value: string) => void;
  inputRef?: React.Ref<HTMLInputElement>;
  onKeyDown?: React.KeyboardEventHandler;
}

const filterToolOptions = createFilterOptions<TimesheetToolOption>({
  stringify: (option) => `${option.label} ${option.searchText}`,
  trim: true,
});

const GROUP_ORDER: Record<string, number> = {
  'MY ASSIGNED PROJECTS': 0,
  'RECENTLY USED': 1,
  'ALL ACTIVE PROJECTS': 2,
  'NON PRODUCTIVE': 3,
};

function ProjectOptionDetail({ option }: { option: TimesheetToolOption }) {
  return (
    <Typography variant="body2" sx={{ py: 0.25, width: '100%' }}>
      {option.label}
    </Typography>
  );
}

export function TimesheetToolNumberSelect({
  label = 'Tool Number',
  value,
  options,
  disabled,
  onChange,
  onInputChange,
  inputRef,
  onKeyDown,
}: TimesheetToolNumberSelectProps) {
  const sortedOptions = [...options].sort(
    (left, right) => (GROUP_ORDER[left.group] ?? 9) - (GROUP_ORDER[right.group] ?? 9),
  );

  return (
    <Autocomplete
      size="small"
      fullWidth
      openOnFocus
      autoHighlight
      handleHomeEndKeys
      disabled={disabled}
      options={sortedOptions}
      value={value}
      groupBy={(option) => option.group}
      getOptionLabel={(option) => option.label}
      isOptionEqualToValue={(left, right) => left.value === right.value}
      filterOptions={filterToolOptions}
      onChange={(_, option) => onChange(option)}
      onInputChange={(_, inputValue, reason) => {
        if (reason === 'input') {
          onInputChange?.(inputValue);
        }
      }}
      noOptionsText="No matching tool numbers or NP codes"
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.value}>
          <ProjectOptionDetail option={option} />
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required
          size="small"
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          placeholder="Search tool number or description…"
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />
      )}
    />
  );
}
