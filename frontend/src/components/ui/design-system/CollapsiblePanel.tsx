import type { ReactNode } from 'react';
import {
  Box,
  Collapse,
  IconButton,
  Paper,
  Typography,
} from '@mui/material';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import type { SvgIconComponent } from '@mui/icons-material';
import { designTokens } from '../../../theme/designTokens';
import { useSessionExpandedSections } from '../../../hooks/useSessionExpandedSections';

interface CollapsiblePanelProps {
  sectionId: string;
  storageKey: string;
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  defaultExpanded?: boolean;
  action?: ReactNode;
  children: ReactNode;
  noPadding?: boolean;
}

export function CollapsiblePanel({
  sectionId,
  storageKey,
  title,
  subtitle,
  icon: Icon,
  defaultExpanded = true,
  action,
  children,
  noPadding = false,
}: CollapsiblePanelProps) {
  const { isExpanded, toggleExpanded } = useSessionExpandedSections(storageKey);
  const expanded = isExpanded(sectionId, defaultExpanded);

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: `${designTokens.radius.lg}px`,
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: designTokens.elevation.card,
        overflow: 'hidden',
        transition: `box-shadow ${designTokens.motion.fast}`,
        '&:hover': { boxShadow: designTokens.elevation.cardHover },
      }}
    >
      <Box
        role="button"
        tabIndex={0}
        onClick={() => toggleExpanded(sectionId, defaultExpanded)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggleExpanded(sectionId, defaultExpanded);
          }
        }}
        sx={{
          px: 2.5,
          py: 2,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 2,
          cursor: 'pointer',
          userSelect: 'none',
          bgcolor: expanded ? designTokens.semantic.neutralSoft : 'background.paper',
          transition: `background-color ${designTokens.motion.fast}`,
          '&:hover': { bgcolor: designTokens.semantic.neutralSoft },
          '&:focus-visible': {
            outline: `2px solid ${designTokens.semantic.primary}`,
            outlineOffset: -2,
          },
        }}
      >
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', minWidth: 0 }}>
          {Icon ? (
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: `${designTokens.radius.md}px`,
                display: 'grid',
                placeItems: 'center',
                bgcolor: designTokens.semantic.primarySoft,
                color: designTokens.semantic.primary,
                flexShrink: 0,
              }}
            >
              <Icon sx={{ fontSize: 20 }} />
            </Box>
          ) : null}
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="sectionTitle" sx={{ letterSpacing: '-0.01em' }}>
              {expanded ? '▼' : '▶'} {title}
            </Typography>
            {subtitle ? (
              <Typography variant="caption" color="text.secondary">
                {subtitle}
              </Typography>
            ) : null}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }} onClick={(e) => e.stopPropagation()}>
          {action}
          <IconButton
            size="small"
            aria-label={expanded ? `Collapse ${title}` : `Expand ${title}`}
            onClick={(event) => {
              event.stopPropagation();
              toggleExpanded(sectionId, defaultExpanded);
            }}
            sx={{
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: `transform ${designTokens.motion.fast}`,
            }}
          >
            <ExpandMoreRoundedIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: noPadding ? 0 : 2.5, pb: noPadding ? 0 : 2.5, pt: noPadding ? 0 : 0.5 }}>
          {children}
        </Box>
      </Collapse>
    </Paper>
  );
}
