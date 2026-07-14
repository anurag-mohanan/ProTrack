import type { ReactNode } from 'react';
import {
  Box,
  FormHelperText,
  TextField,
  Typography,
  type TextFieldProps,
} from '@mui/material';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { HelpTooltip } from './HelpTooltip';

interface FormFieldProps extends Omit<TextFieldProps, 'variant'> {
  helper?: ReactNode;
  maxLength?: number;
  tooltip?: string;
  validationState?: 'success' | 'warning';
  validationMessage?: string;
}

export function FormField({
  helper,
  maxLength,
  value,
  error,
  tooltip,
  validationState,
  validationMessage,
  ...props
}: FormFieldProps) {
  const stringValue = typeof value === 'string' ? value : '';
  const showCounter = maxLength !== undefined;
  const hasValue =
    value !== '' && value !== null && value !== undefined && !(Array.isArray(value) && value.length === 0);

  const ValidationIcon =
    validationState === 'success'
      ? CheckCircleOutlineRoundedIcon
      : validationState === 'warning'
        ? WarningAmberRoundedIcon
        : null;

  return (
    <Box>
      {tooltip ? (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: -0.5, mr: 0.25, position: 'relative', zIndex: 1 }}>
          <HelpTooltip title={tooltip} />
        </Box>
      ) : null}
      <TextField
        {...props}
        label={props.label}
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
          inputLabel: {
            shrink: hasValue || props.focused || undefined,
            ...props.slotProps?.inputLabel,
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
      {(helper || showCounter || validationMessage) && (
        <FormHelperText error={error} sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
            {ValidationIcon ? (
              <ValidationIcon
                fontSize="inherit"
                color={validationState === 'success' ? 'success' : 'warning'}
              />
            ) : null}
            <Typography
              component="span"
              variant="caption"
              color={validationState === 'success' ? 'success.main' : undefined}
            >
              {validationMessage || helper}
            </Typography>
          </Box>
          {showCounter ? (
            <span>
              {stringValue.length}/{maxLength}
            </span>
          ) : null}
        </FormHelperText>
      )}
    </Box>
  );
}
