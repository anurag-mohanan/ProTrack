import { Stack } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import HistoryIcon from '@mui/icons-material/History';
import FileCopyOutlinedIcon from '@mui/icons-material/FileCopyOutlined';
import { ProsohmButton } from '../ui/ProsohmButton';

interface TimesheetQuickActionsProps {
  readOnly: boolean;
  loading: boolean;
  hasSelectedEntry: boolean;
  onCopyYesterday: () => void;
  onCopyPreviousWeek: () => void;
  onDuplicateSelected: () => void;
}

export function TimesheetQuickActions({
  readOnly,
  loading,
  hasSelectedEntry,
  onCopyYesterday,
  onCopyPreviousWeek,
  onDuplicateSelected,
}: TimesheetQuickActionsProps) {
  if (readOnly) return null;

  return (
    <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
      <ProsohmButton
        buttonVariant="outlined"
        size="small"
        startIcon={<HistoryIcon />}
        disabled={loading}
        onClick={onCopyYesterday}
      >
        Copy Yesterday
      </ProsohmButton>
      <ProsohmButton
        buttonVariant="outlined"
        size="small"
        startIcon={<ContentCopyIcon />}
        disabled={loading}
        onClick={onCopyPreviousWeek}
      >
        Copy Previous Week
      </ProsohmButton>
      <ProsohmButton
        buttonVariant="outlined"
        size="small"
        startIcon={<FileCopyOutlinedIcon />}
        disabled={loading || !hasSelectedEntry}
        onClick={onDuplicateSelected}
      >
        Duplicate Selected Entry
      </ProsohmButton>
    </Stack>
  );
}
