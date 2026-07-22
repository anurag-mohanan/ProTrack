import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
  /** Cap content width on ultrawide monitors (keeps readable line lengths). */
  maxWidth?: number | false;
  sx?: SxProps<Theme>;
}

export function PageContainer({
  children,
  maxWidth = false,
  sx,
}: PageContainerProps) {
  return (
    <Box
      sx={{
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
        ...(maxWidth ? { maxWidth, mx: 'auto' } : null),
        animation: 'prosohmPageIn 0.28s ease-out',
        '@keyframes prosohmPageIn': {
          from: { opacity: 0, transform: 'translateY(6px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}
