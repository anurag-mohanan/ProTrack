import type { ReactNode } from 'react';
import { Box, Stack } from '@mui/material';
import { designTokens } from '../../../../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from '../StickyRecordHeader';
import { ActiveFilterChips, type ActiveFilterChip } from './ActiveFilterChips';
import { FilterButton } from './FilterButton';

interface FilterToolbarProps {
  children?: ReactNode;
  sticky?: boolean;
  dense?: boolean;
  filterButton?: {
    activeCount?: number;
    onClick: () => void;
  };
  chips?: ActiveFilterChip[];
  onClearAll?: () => void;
}

export function FilterToolbar({
  children,
  sticky = false,
  dense = false,
  filterButton,
  chips = [],
  onClearAll,
}: FilterToolbarProps) {
  return (
    <Box
      sx={{
        mb: dense ? 0.75 : 1.5,
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
      <Stack
        direction="row"
        spacing={1}
        sx={{ flexWrap: 'wrap', alignItems: 'center', rowGap: dense ? 0.5 : 1 }}
      >
        {children}
        {filterButton ? (
          <FilterButton activeCount={filterButton.activeCount} onClick={filterButton.onClick} />
        ) : null}
      </Stack>
      {chips.length > 0 ? (
        <Box sx={{ mt: dense ? 0.5 : 1 }}>
          <ActiveFilterChips chips={chips} onClearAll={onClearAll} />
        </Box>
      ) : null}
    </Box>
  );
}
