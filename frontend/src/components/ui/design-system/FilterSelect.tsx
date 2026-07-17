import {
  FormControl,
  InputLabel,
  Select,
  type SelectChangeEvent,
  type SelectProps,
  type SxProps,
  type Theme,
} from '@mui/material';
import type { ReactNode } from 'react';

type FilterSelectProps = Omit<
  SelectProps<string>,
  'variant' | 'label' | 'displayEmpty' | 'notched' | 'sx' | 'onChange'
> & {
  label: string;
  children: ReactNode;
  /** Defaults to small for filter bars / compact create panels. */
  size?: 'small' | 'medium';
  /** Applied to the outer FormControl (e.g. minWidth). */
  sx?: SxProps<Theme>;
  onChange?: (event: SelectChangeEvent<string>, child?: ReactNode) => void;
};

/**
 * Outlined select for filters and create panels that allow an empty value
 * (e.g. "All teams", "Select member"). Always shrinks the floating label so it
 * never stacks on top of the empty-option text — the classic MUI overlap bug.
 */
export function FilterSelect({
  label,
  children,
  size = 'small',
  fullWidth = true,
  value,
  sx,
  onChange,
  ...props
}: FilterSelectProps) {
  const valueStr = value === null || value === undefined ? '' : String(value);
  return (
    <FormControl size={size} fullWidth={fullWidth} disabled={props.disabled} sx={sx}>
      <InputLabel shrink>{label}</InputLabel>
      <Select
        {...props}
        label={label}
        value={valueStr}
        displayEmpty
        notched
        onChange={onChange}
      >
        {children}
      </Select>
    </FormControl>
  );
}
