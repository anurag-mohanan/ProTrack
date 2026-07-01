import {
  Autocomplete,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  type SelectProps,
} from '@mui/material';

export interface SelectOption {
  value: string;
  label: string;
}

interface FormSelectProps extends Omit<SelectProps, 'variant'> {
  label: string;
  options: SelectOption[];
  searchable?: boolean;
  placeholder?: string;
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
  ...props
}: FormSelectProps) {
  if (searchable) {
    const selected = options.find((option) => option.value === value) ?? null;
    return (
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
            label={label}
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
    );
  }

  return (
    <FormControl fullWidth required={required} disabled={disabled}>
      <InputLabel>{label}</InputLabel>
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
    </FormControl>
  );
}
