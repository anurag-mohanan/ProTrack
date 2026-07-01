import type { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  action?: ReactNode;
}

export function SectionHeader({ title, subtitle, icon: Icon, action }: SectionHeaderProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 2,
        mb: subtitle ? 1 : 0,
      }}
    >
      <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'center', minWidth: 0 }}>
        {Icon ? (
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: 2,
              display: 'grid',
              placeItems: 'center',
              bgcolor: 'action.hover',
              color: 'primary.main',
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 18 }} />
          </Box>
        ) : null}
        <Box>
          <Typography variant="sectionTitle">{title}</Typography>
          {subtitle ? (
            <Typography variant="captionLabel" color="text.secondary">
              {subtitle}
            </Typography>
          ) : null}
        </Box>
      </Box>
      {action}
    </Box>
  );
}
