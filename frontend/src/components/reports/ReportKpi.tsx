import type { ReactNode } from 'react';
import { Box, Paper, Tooltip, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

interface KpiCardProps {
  label: string;
  value: string;
  caption?: ReactNode;
  definition?: string;
  onClick?: () => void;
  selected?: boolean;
}

export function KpiCard({ label, value, caption, definition, onClick, selected = false }: KpiCardProps) {
  return (
    <Paper
      variant="outlined"
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      sx={{
        p: 1.75,
        minWidth: 0,
        cursor: onClick ? 'pointer' : undefined,
        borderColor: selected ? 'primary.main' : undefined,
        '&:hover': onClick ? { borderColor: 'primary.light' } : undefined,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        {definition ? (
          <Tooltip title={definition}>
            <InfoOutlinedIcon sx={{ fontSize: 14, color: 'text.disabled' }} aria-label={`${label} definition`} />
          </Tooltip>
        ) : null}
      </Box>
      <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.3 }}>
        {value}
      </Typography>
      {caption ? (
        <Typography variant="caption" color="text.secondary">
          {caption}
        </Typography>
      ) : null}
    </Paper>
  );
}

export function SectionTitle({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
        {title}
      </Typography>
      {subtitle ? (
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      ) : null}
    </Box>
  );
}
