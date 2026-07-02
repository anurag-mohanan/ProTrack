import { Box, Typography } from '@mui/material';
import {
  COPYRIGHT_NOTICE,
  PRODUCT_NAME,
  RELEASE_LABEL,
  VERSION_DISPLAY,
} from '../../config/appMeta';

interface AppFooterProps {
  compact?: boolean;
}

export function AppFooter({ compact = false }: AppFooterProps) {
  return (
    <Box
      component="footer"
      sx={{
        mt: 'auto',
        py: compact ? 1.5 : 2,
        px: { xs: 2, md: 3 },
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        textAlign: 'center',
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontWeight: 600 }}>
        {PRODUCT_NAME} {VERSION_DISPLAY}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {RELEASE_LABEL}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
        {COPYRIGHT_NOTICE}
      </Typography>
    </Box>
  );
}
