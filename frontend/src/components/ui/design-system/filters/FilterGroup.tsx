import { useState, type ReactNode } from 'react';
import { Box, Collapse, Typography } from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';

interface FilterGroupProps {
  title: string;
  icon?: ReactNode;
  defaultExpanded?: boolean;
  children: ReactNode;
}

export function FilterGroup({
  title,
  icon,
  defaultExpanded = false,
  children,
}: FilterGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
      <Box
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setExpanded((current) => !current);
          }
        }}
        sx={{
          py: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        {icon}
        <Typography variant="caption" sx={{ fontWeight: 700, flex: 1, letterSpacing: '0.02em' }}>
          {title}
        </Typography>
        <ExpandMoreRoundedIcon
          sx={{
            fontSize: 18,
            color: 'text.secondary',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }}
        />
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ pb: 1.25, display: 'flex', flexDirection: 'column', gap: 1 }}>{children}</Box>
      </Collapse>
    </Box>
  );
}
