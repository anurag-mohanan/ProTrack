import type { ReactNode } from 'react';
import { Box } from '@mui/material';
import { ContentCard } from '../cards';

interface SearchToolbarProps {
  children: ReactNode;
}

export function SearchToolbar({ children }: SearchToolbarProps) {
  return (
    <Box sx={{ mb: 2.5 }}>
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
