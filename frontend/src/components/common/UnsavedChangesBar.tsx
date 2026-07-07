import { Box, Paper, Typography } from '@mui/material';
import { ProsohmButton } from '../ui/ProsohmButton';
import { designTokens } from '../../theme/designTokens';

interface UnsavedChangesBarProps {
  visible: boolean;
  onSave: () => void;
  onDiscard: () => void;
  saving?: boolean;
  saveDisabled?: boolean;
  saveLabel?: string;
  message?: string;
  inset?: boolean;
}

export function UnsavedChangesBar({
  visible,
  onSave,
  onDiscard,
  saving = false,
  saveDisabled = false,
  saveLabel = 'Save Changes',
  message = 'You have unsaved changes',
  inset = false,
}: UnsavedChangesBarProps) {
  if (!visible) return null;

  return (
    <Box
      sx={{
        position: inset ? 'sticky' : 'fixed',
        bottom: inset ? 0 : 24,
        left: inset ? 0 : { xs: 16, sm: '50%' },
        right: inset ? 0 : { xs: 16, sm: 'auto' },
        transform: inset ? 'none' : { sm: 'translateX(-50%)' },
        zIndex: (theme) => theme.zIndex.snackbar,
        display: 'flex',
        justifyContent: 'center',
        pointerEvents: 'none',
        mt: inset ? 2 : 0,
      }}
    >
      <Paper
        elevation={8}
        sx={{
          pointerEvents: 'auto',
          px: 2.5,
          py: 1.5,
          borderRadius: `${designTokens.radius.lg}px`,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
          border: 1,
          borderColor: 'divider',
          boxShadow: designTokens.elevation.cardHover,
          width: inset ? '100%' : { xs: '100%', sm: 'auto' },
          justifyContent: { xs: 'space-between', sm: 'flex-start' },
          animation: 'unsavedBarIn 0.22s ease-out',
          '@keyframes unsavedBarIn': {
            from: { opacity: 0, transform: 'translateY(12px)' },
            to: { opacity: 1, transform: 'translateY(0)' },
          },
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600, px: 0.5 }}>
          {message}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <ProsohmButton buttonVariant="outlined" size="small" onClick={onDiscard} disabled={saving}>
            Discard
          </ProsohmButton>
          <ProsohmButton
            buttonVariant="primary"
            size="small"
            onClick={onSave}
            loading={saving}
            disabled={saveDisabled || saving}
          >
            {saveLabel}
          </ProsohmButton>
        </Box>
      </Paper>
    </Box>
  );
}
