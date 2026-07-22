import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface PageHeaderProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
}

/** Page title is shown in the top bar; this block is for subtitle and actions only. */
export function PageHeader({ subtitle, action }: PageHeaderProps) {
  if (!subtitle && !action) {
    return null;
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: { xs: 'flex-start', sm: 'center' },
        flexDirection: { xs: 'column', sm: 'row' },
        gap: 2,
        mb: 2,
      }}
    >
      {subtitle ? (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ minWidth: 0, flex: 1, pr: { sm: 2 }, wordBreak: 'break-word' }}
        >
          {subtitle}
        </Typography>
      ) : (
        <Box />
      )}
      {action ? <Box sx={{ flexShrink: 0, width: { xs: '100%', sm: 'auto' } }}>{action}</Box> : null}
    </Box>
  );
}
