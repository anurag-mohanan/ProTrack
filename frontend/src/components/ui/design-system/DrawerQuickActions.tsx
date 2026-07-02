import type { ReactNode } from 'react';
import { Box } from '@mui/material';

interface DrawerQuickActionsProps {
  children: ReactNode;
}

export function DrawerQuickActions({ children }: DrawerQuickActionsProps) {
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
      {children}
    </Box>
  );
}
