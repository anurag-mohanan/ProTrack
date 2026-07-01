import type { ReactNode } from 'react';
import { Box, Paper, useTheme } from '@mui/material';
import { SectionHeader } from './SectionHeader';
import type { SvgIconComponent } from '@mui/icons-material';

interface AppCardProps {
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  action?: ReactNode;
  children: ReactNode;
  noPadding?: boolean;
}

export function AppCard({
  title,
  subtitle,
  icon,
  action,
  children,
  noPadding = false,
}: AppCardProps) {
  const theme = useTheme();

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: 3,
        border: `1px solid ${theme.palette.prosohm.border}`,
        boxShadow: theme.palette.prosohm.shadowCard,
        overflow: 'hidden',
        transition: 'box-shadow 0.2s ease',
        '&:hover': {
          boxShadow: theme.palette.prosohm.shadowCardHover,
        },
      }}
    >
      <Box sx={{ px: 2.5, pt: 2.5, pb: noPadding ? 0 : 2.5 }}>
        <SectionHeader title={title} subtitle={subtitle} icon={icon} action={action} />
      </Box>
      <Box sx={{ px: noPadding ? 0 : 2.5, pb: noPadding ? 0 : 2.5 }}>{children}</Box>
    </Paper>
  );
}
