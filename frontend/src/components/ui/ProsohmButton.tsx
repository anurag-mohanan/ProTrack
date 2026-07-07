import type { ReactNode } from 'react';
import {
  Box,
  Button,
  type ButtonProps,
  CircularProgress,
} from '@mui/material';

type ProsohmButtonVariant = 'primary' | 'secondary' | 'outlined' | 'danger' | 'success';

interface ProsohmButtonProps extends Omit<ButtonProps, 'color' | 'variant'> {
  buttonVariant?: ProsohmButtonVariant;
  loading?: boolean;
}

const variantMap: Record<
  ProsohmButtonVariant,
  Pick<ButtonProps, 'variant' | 'color'>
> = {
  primary: { variant: 'contained', color: 'primary' },
  secondary: { variant: 'contained', color: 'secondary' },
  outlined: { variant: 'outlined', color: 'primary' },
  danger: { variant: 'contained', color: 'error' },
  success: { variant: 'contained', color: 'success' },
};

export function ProsohmButton({
  buttonVariant = 'primary',
  loading = false,
  children,
  disabled,
  startIcon,
  ...props
}: ProsohmButtonProps) {
  const mapped = variantMap[buttonVariant];

  return (
    <Button
      {...mapped}
      {...props}
      disabled={disabled || loading}
      startIcon={loading ? <CircularProgress size={16} color="inherit" /> : startIcon}
      sx={{
        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
        '&:hover:not(:disabled)': { transform: 'translateY(-1px)' },
        ...props.sx,
      }}
    >
      {children}
    </Button>
  );
}

interface ProsohmButtonGroupProps {
  children: ReactNode;
  align?: 'left' | 'right';
}

export function ProsohmButtonGroup({
  children,
  align = 'right',
}: ProsohmButtonGroupProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1,
        justifyContent: align === 'right' ? 'flex-end' : 'flex-start',
        flexWrap: 'wrap',
      }}
    >
      {children}
    </Box>
  );
}
