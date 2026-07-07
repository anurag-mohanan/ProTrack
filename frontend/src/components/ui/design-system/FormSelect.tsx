import {
  Autocomplete,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  type SelectProps,
} from '@mui/material';
import { Box } from '@mui/material';
import { HelpTooltip } from './HelpTooltip';

export interface SelectOption {
  value: string;
  label: string;
}

interface FormSelectProps extends Omit<SelectProps, 'variant'> {
  label: string;
  options: SelectOption[];
  searchable?: boolean;
  placeholder?: string;
  helper?: string;
  tooltip?: string;
}

export function FormSelect({
  label,
  options,
  searchable = false,
  value,
  onChange,
  disabled,
  required,
  placeholder,
  helper,
  tooltip,
  ...props
}: FormSelectProps) {
  const labelWithTooltip = tooltip ? (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center' }}>
      {label}
      <HelpTooltip title={tooltip} />
    </Box>
  ) : (
    label
  );

  if (searchable) {
    const selected = options.find((option) => option.value === value) ?? null;
    return (
      <Box>
        <Autocomplete
          options={options}
          value={selected}
          disabled={disabled}
          getOptionLabel={(option) => option.label}
          isOptionEqualToValue={(a, b) => a.value === b.value}
          onChange={(_, option) => {
            onChange?.(
              { target: { value: option?.value ?? '' } } as never,
              null as never,
            );
          }}
          renderInput={(params) => (
            <TextField
              {...params}
              label={labelWithTooltip}
              required={required}
              placeholder={placeholder}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 2.5,
                },
              }}
            />
          )}
        />
        {helper ? <FormHelperText>{helper}</FormHelperText> : null}
      </Box>
    );
  }

  return (
    <FormControl fullWidth required={required} disabled={disabled}>
      <InputLabel>{labelWithTooltip}</InputLabel>
      <Select
        {...props}
        label={label}
        value={value ?? ''}
        onChange={onChange}
        sx={{
          borderRadius: 2.5,
          ...props.sx,
        }}
      >
        {options.map((option) => (
          <MenuItem key={option.value} value={option.value}>
            {option.label}
          </MenuItem>
        ))}
      </Select>
      {helper ? <FormHelperText>{helper}</FormHelperText> : null}
    </FormControl>
  );
}
