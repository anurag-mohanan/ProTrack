import { Box, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';
import { designTokens } from '../../theme/designTokens';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <Box
      sx={{
        py: 6,
        px: 3,
        textAlign: 'center',
        border: '1px dashed',
        borderColor: 'divider',
        borderRadius: `${designTokens.radius.lg}px`,
        bgcolor: designTokens.semantic.card,
        boxShadow: designTokens.elevation.card,
      }}
    >
      <Box
        sx={{
          width: 72,
          height: 72,
          borderRadius: '50%',
          mx: 'auto',
          mb: 2,
          display: 'grid',
          placeItems: 'center',
          bgcolor: designTokens.semantic.primarySoft,
          color: designTokens.semantic.primary,
        }}
      >
        {icon ?? <InboxOutlinedIcon sx={{ fontSize: 36 }} />}
      </Box>
      <Typography variant="h6" gutterBottom sx={{ fontWeight: 700 }}>
        {title}
      </Typography>
      {description ? (
        <Typography color="text.secondary" sx={{ mb: action ? 2.5 : 0, maxWidth: 420, mx: 'auto' }}>
          {description}
        </Typography>
      ) : null}
      {action}
    </Box>
  );
}
