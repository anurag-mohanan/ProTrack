import { useId, useState } from 'react';
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

interface FormSelectProps extends Omit<SelectProps, 'variant' | 'label'> {
  label: string;
  options: SelectOption[];
  searchable?: boolean;
  placeholder?: string;
  helper?: string;
  tooltip?: string;
  /** Display label when `value` is not yet present in `options`. */
  selectedLabel?: string | null;
}

/**
 * Shared select for create/edit forms.
 * Keep the floating label as a plain string (tooltip sits outside) so the outline
 * notch width matches and selected values never collide with the label.
 */
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
  selectedLabel,
  ...props
}: FormSelectProps) {
  const labelId = useId();
  const [open, setOpen] = useState(false);
  const hasValue = value !== '' && value !== null && value !== undefined;
  // Notch whenever open, valued, or showing a placeholder — stops label/value stack.
  const shrink = open || hasValue || Boolean(placeholder);

  const helpAffordance = tooltip ? (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: -0.5, mr: 0.25, position: 'relative', zIndex: 1 }}>
      <HelpTooltip title={tooltip} />
    </Box>
  ) : null;

  if (searchable) {
    const valueStr = value === null || value === undefined ? '' : String(value);
    const matched = options.find((option) => String(option.value) === valueStr) ?? null;
    // Keep current selection visible even if lookups omit it (inactive, pagination, etc.).
    const selected =
      matched ??
      (valueStr
        ? {
            value: valueStr,
            label: selectedLabel?.trim() || valueStr,
          }
        : null);
    const mergedOptions =
      selected && !matched ? [selected, ...options.filter((o) => String(o.value) !== valueStr)] : options;

    return (
      <Box>
        {helpAffordance}
        <Autocomplete
          options={mergedOptions}
          value={selected}
          disabled={disabled}
          getOptionLabel={(option) => option.label}
          isOptionEqualToValue={(a, b) => String(a.value) === String(b.value)}
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
              slotProps={{
                inputLabel: {
                  shrink: Boolean(selected) || Boolean(placeholder) || undefined,
                },
              }}
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
    <Box>
      {helpAffordance}
      <FormControl fullWidth required={required} disabled={disabled}>
        <InputLabel id={labelId} shrink={shrink}>
          {label}
        </InputLabel>
        <Select
          {...props}
          labelId={labelId}
          label={label}
          notched={shrink}
          value={value ?? ''}
          displayEmpty={Boolean(placeholder)}
          open={open}
          onOpen={(event) => {
            setOpen(true);
            props.onOpen?.(event);
          }}
          onClose={(event) => {
            setOpen(false);
            props.onClose?.(event);
          }}
          onChange={onChange}
          sx={{
            borderRadius: 2.5,
            ...props.sx,
          }}
        >
          {placeholder ? (
            <MenuItem value="">
              <em>{placeholder}</em>
            </MenuItem>
          ) : null}
          {options.map((option) => (
            <MenuItem key={option.value || '__none__'} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </Select>
        {helper ? <FormHelperText>{helper}</FormHelperText> : null}
      </FormControl>
    </Box>
  );
}
