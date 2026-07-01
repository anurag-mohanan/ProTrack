import type { ReactNode } from 'react';
import {
  FormHelperText,
  TextField,
  type TextFieldProps,
} from '@mui/material';

interface FormFieldProps extends Omit<TextFieldProps, 'variant'> {
  helper?: ReactNode;
  maxLength?: number;
}

export function FormField({
  helper,
  maxLength,
  value,
  error,
  ...props
}: FormFieldProps) {
  const stringValue = typeof value === 'string' ? value : '';
  const showCounter = maxLength !== undefined;

  return (
    <>
      <TextField
        {...props}
        value={value}
        error={error}
        variant="outlined"
        fullWidth={props.fullWidth ?? true}
        slotProps={{
          ...props.slotProps,
          htmlInput: {
            maxLength,
            ...props.slotProps?.htmlInput,
          },
        }}
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: 2.5,
            transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
            '&.Mui-focused': {
              boxShadow: (theme) => `0 0 0 3px ${theme.palette.primary.main}22`,
            },
          },
          ...props.sx,
        }}
      />
      {(helper || showCounter) && (
        <FormHelperText error={error} sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>{helper}</span>
          {showCounter ? (
            <span>
              {stringValue.length}/{maxLength}
            </span>
          ) : null}
        </FormHelperText>
      )}
    </>
  );
}
