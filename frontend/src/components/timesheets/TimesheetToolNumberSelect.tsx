import {
  Autocomplete,
  ListSubheader,
  TextField,
} from '@mui/material';
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
      options={options}
      value={value}
      disabled={disabled}
      groupBy={(option) => option.group}
      getOptionLabel={(option) => option.label}
      isOptionEqualToValue={(left, right) => left.value === right.value}
      filterOptions={(items, state) => {
        const term = state.inputValue.trim().toLowerCase();
        if (!term) return items;
        return items.filter(
          (item) =>
            item.searchText.includes(term) || item.label.toLowerCase().includes(term),
        );
      }}
      onChange={(_, option) => onChange(option)}
      renderGroup={(params) => (
        <li key={params.key}>
          <ListSubheader
            sx={{
              bgcolor: 'background.default',
              fontWeight: 700,
              fontSize: '0.7rem',
              lineHeight: 2.2,
              letterSpacing: '0.06em',
            }}
          >
            {params.group}
          </ListSubheader>
          <ul style={{ padding: 0 }}>{params.children}</ul>
        </li>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required
          size="small"
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          placeholder="Search…"
          slotProps={{
            htmlInput: {
              autoComplete: 'off',
            },
          }}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />
      )}
    />
  );
}
