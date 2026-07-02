import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
  maxWidth?: number;
  sx?: SxProps<Theme>;
}

export function PageContainer({
  children,
  maxWidth = 1360,
  sx,
}: PageContainerProps) {
  return (
    <Box
      sx={{
        maxWidth,
        mx: 'auto',
        width: '100%',
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
