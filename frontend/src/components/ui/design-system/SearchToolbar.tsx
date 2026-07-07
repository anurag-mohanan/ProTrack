import type { ReactNode } from 'react';
import { Box } from '@mui/material';
import { ContentCard } from '../cards';
import { designTokens } from '../../../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from './StickyRecordHeader';

interface SearchToolbarProps {
  children: ReactNode;
  sticky?: boolean;
}

export function SearchToolbar({ children, sticky = false }: SearchToolbarProps) {
  return (
    <Box
      sx={{
        mb: 2.5,
        ...(sticky
          ? {
              position: 'sticky',
              top: APP_TOP_BAR_OFFSET,
              zIndex: 4,
              py: 1,
              bgcolor: designTokens.semantic.background,
            }
          : null),
      }}
    >
      <ContentCard>
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {children}
        </Box>
      </ContentCard>
    </Box>
  );
}
