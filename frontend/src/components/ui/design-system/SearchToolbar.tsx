import type { ReactNode } from 'react';
import { Box } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from './StickyRecordHeader';

interface SearchToolbarProps {
  children: ReactNode;
  sticky?: boolean;
}

/** @deprecated Prefer FilterToolbar for list pages with filters. */
export function SearchToolbar({ children, sticky = false }: SearchToolbarProps) {
  return (
    <Box
      sx={{
        mb: 1.5,
        display: 'flex',
        gap: 1,
        flexWrap: 'wrap',
        alignItems: 'center',
        ...(sticky
          ? {
              position: 'sticky',
              top: APP_TOP_BAR_OFFSET,
              zIndex: 4,
              py: 0.75,
              bgcolor: designTokens.semantic.background,
            }
          : null),
      }}
    >
      {children}
    </Box>
  );
}
