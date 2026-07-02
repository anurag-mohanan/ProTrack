import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
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
