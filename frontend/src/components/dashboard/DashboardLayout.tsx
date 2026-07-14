import { Box } from '@mui/material';
import type { ReactNode } from 'react';

interface DashboardLayoutProps {
  children: ReactNode;
  sidebar?: ReactNode;
}

export function DashboardLayout({ children, sidebar }: DashboardLayoutProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 2,
        flexDirection: { xs: 'column', lg: 'row' },
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0, width: '100%' }}>{children}</Box>
      {sidebar ? (
        <Box
          sx={{
            width: { xs: '100%', lg: 320 },
            flexShrink: 0,
            position: { lg: 'sticky' },
            top: { lg: 72 },
            alignSelf: 'flex-start',
            maxHeight: { lg: 'calc(100vh - 88px)' },
            overflowY: { lg: 'auto' },
            pb: { lg: 2 },
            pr: { lg: 0.5 },
            // Keep last rail card fully visible when scrolling.
            scrollbarGutter: 'stable',
          }}
        >
          {sidebar}
        </Box>
      ) : null}
    </Box>
  );
}
