import type { ReactNode } from 'react';
import {
  Box,
  Collapse,
  Grid,
  IconButton,
  Paper,
  Typography,
  useTheme,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { SvgIconComponent } from '@mui/icons-material';
import { useSessionExpandedSections } from '../../../hooks/useSessionExpandedSections';

interface CollapsibleFormSectionProps {
  sectionId: string;
  storageKey: string;
  title: string;
  subtitle?: string;
  icon?: SvgIconComponent;
  defaultExpanded?: boolean;
  children: ReactNode;
}

export function CollapsibleFormSection({
  sectionId,
  storageKey,
  title,
  subtitle,
  icon: Icon,
  defaultExpanded = true,
  children,
}: CollapsibleFormSectionProps) {
  const theme = useTheme();
  const { isExpanded, toggleExpanded } = useSessionExpandedSections(storageKey);
  const expanded = isExpanded(sectionId, defaultExpanded);

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: 3,
        border: `1px solid ${theme.palette.prosohm.border}`,
        boxShadow: theme.palette.prosohm.shadowCard,
        overflow: 'hidden',
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
          '&:hover': { bgcolor: 'action.hover' },
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
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="sectionTitle">{title}</Typography>
            {subtitle ? (
              <Typography variant="captionLabel" color="text.secondary">
                {subtitle}
              </Typography>
            ) : null}
          </Box>
        </Box>
        <IconButton
          size="small"
          aria-label={expanded ? `Collapse ${title}` : `Expand ${title}`}
          onClick={(event) => {
            event.stopPropagation();
            toggleExpanded(sectionId, defaultExpanded);
          }}
          sx={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2.5, pb: 2.5 }}>
          <Grid container spacing={2.5}>
            {children}
          </Grid>
        </Box>
      </Collapse>
    </Paper>
  );
}
