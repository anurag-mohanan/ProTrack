import type { ReactNode } from 'react';
import { Box } from '@mui/material';
import { APP_TOP_BAR_OFFSET, StickyRecordHeader } from '../ui/design-system/StickyRecordHeader';
import { UnsavedChangesBar } from './UnsavedChangesBar';

interface StickyFormPageLayoutProps {
  children: ReactNode;
  header: ReactNode;
  dirty?: boolean;
  onSave?: () => void;
  onDiscard?: () => void;
  saving?: boolean;
  saveDisabled?: boolean;
  saveLabel?: string;
  bottomPadding?: number;
}

export function StickyFormPageLayout({
  children,
  header,
  dirty = false,
  onSave,
  onDiscard,
  saving = false,
  saveDisabled = false,
  saveLabel,
  bottomPadding = 96,
}: StickyFormPageLayoutProps) {
  return (
    <Box sx={{ pb: dirty ? bottomPadding / 8 : 0 }}>
      <Box sx={{ mb: 2 }}>{header}</Box>
      {children}
      {onSave && onDiscard ? (
        <UnsavedChangesBar
          visible={dirty}
          onSave={onSave}
          onDiscard={onDiscard}
          saving={saving}
          saveDisabled={saveDisabled}
          saveLabel={saveLabel}
        />
      ) : null}
    </Box>
  );
}

export { StickyRecordHeader, APP_TOP_BAR_OFFSET };
