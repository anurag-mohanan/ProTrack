import { useState, type ReactNode } from 'react';
import { Box, Chip, Collapse, IconButton, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { designTokens } from '../../../theme/designTokens';

interface ProjectStreamPanelProps {
  streamName: string;
  projectCount: number;
  defaultExpanded?: boolean;
  /** When false, render children without the stream chrome (single-stream focus). */
  showChrome?: boolean;
  children: ReactNode;
}

const STREAM_ACCENTS = [
  designTokens.semantic.primary,
  '#0d9488',
  '#7c3aed',
  '#c2410c',
  '#0369a1',
] as const;

function accentForName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash + name.charCodeAt(i) * (i + 1)) % STREAM_ACCENTS.length;
  }
  return STREAM_ACCENTS[hash] ?? STREAM_ACCENTS[0];
}

export function ProjectStreamPanel({
  streamName,
  projectCount,
  defaultExpanded = true,
  showChrome = true,
  children,
}: ProjectStreamPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const accent = accentForName(streamName);

  if (!showChrome) {
    return <Box sx={{ mb: 1.25 }}>{children}</Box>;
  }

  return (
    <Box
      sx={{
        mb: 1.5,
        borderRadius: `${designTokens.radius.md}px`,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        overflow: 'hidden',
        boxShadow: designTokens.elevation.card,
      }}
    >
      <Box
        component="button"
        type="button"
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
        sx={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.25,
          py: 0.85,
          m: 0,
          border: 0,
          cursor: 'pointer',
          textAlign: 'left',
          bgcolor: 'transparent',
          borderLeft: `3px solid ${accent}`,
          '&:hover': { bgcolor: designTokens.semantic.neutralSoft },
        }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 700,
              letterSpacing: '-0.01em',
              lineHeight: 1.2,
              color: 'text.primary',
            }}
          >
            {streamName}
          </Typography>
        </Box>
        <Chip
          size="small"
          label={projectCount}
          sx={{
            height: 22,
            fontWeight: 700,
            fontSize: '0.72rem',
            bgcolor: `${accent}14`,
            color: accent,
            borderRadius: `${designTokens.radius.sm}px`,
          }}
        />
        <IconButton
          size="small"
          tabIndex={-1}
          aria-hidden
          sx={{
            p: 0.25,
            transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
            transition: `transform ${designTokens.motion.fast}`,
          }}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={expanded} timeout="auto" unmountOnExit={false}>
        <Box
          sx={{
            px: 1,
            pb: 1,
            pt: 0.25,
            borderTop: '1px solid',
            borderColor: 'divider',
            bgcolor: designTokens.semantic.background,
          }}
        >
          {children}
        </Box>
      </Collapse>
    </Box>
  );
}
