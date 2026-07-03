import { Autocomplete, TextField, createFilterOptions } from '@mui/material';
import type { TimesheetToolOption } from './timesheetToolOptions';

interface TimesheetToolNumberSelectProps {
  label?: string;
  value: TimesheetToolOption | null;
  options: TimesheetToolOption[];
  disabled?: boolean;
  onChange: (option: TimesheetToolOption | null) => void;
  inputRef?: React.Ref<HTMLInputElement>;
  onKeyDown?: React.KeyboardEventHandler;
}

const filterToolOptions = createFilterOptions<TimesheetToolOption>({
  stringify: (option) => `${option.label} ${option.searchText}`,
  trim: true,
});

export function TimesheetToolNumberSelect({
  label = 'Tool Number',
  value,
  options,
  disabled,
  onChange,
  inputRef,
  onKeyDown,
}: TimesheetToolNumberSelectProps) {
  return (
    <Autocomplete
      size="small"
      fullWidth
      openOnFocus
      autoHighlight
      handleHomeEndKeys
      disabled={disabled}
      options={options}
      value={value}
      groupBy={(option) => option.group}
      getOptionLabel={(option) => option.label}
      isOptionEqualToValue={(left, right) => left.value === right.value}
      filterOptions={filterToolOptions}
      onChange={(_, option) => onChange(option)}
      noOptionsText="No matching tool numbers or NP codes"
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required
          size="small"
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          placeholder="Search tool number, part, customer or NP code…"
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />
      )}
    />
  );
}
