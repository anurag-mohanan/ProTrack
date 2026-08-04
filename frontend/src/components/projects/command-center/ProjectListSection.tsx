import { useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { Customer, Project, Stream, Team, User } from '../../../types';
import type { ProjectTableRow } from '../ProjectTable';
import { ProjectBoardList } from './ProjectBoardList';

interface ProjectListSectionProps {
  title: string;
  count: number;
  projects: Project[];
  customers: Customer[];
  users: User[];
  streams: Stream[];
  teams: Team[];
  defaultExpanded?: boolean;
  collapsible?: boolean;
  primary?: boolean;
  /** Quieter header for team groups nested under a stream panel. */
  nested?: boolean;
  gridSessionKey?: number;
  splitActiveHold?: boolean;
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onDuplicate?: (projectId: string) => void;
  onExport?: (row: ProjectTableRow) => void;
  onDelete?: (projectId: string) => void;
  canDelete?: boolean;
}

export function ProjectListSection({
  title,
  count,
  projects,
  customers,
  users,
  streams,
  teams,
  defaultExpanded = true,
  collapsible = false,
  nested = false,
  splitActiveHold = true,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  canDelete,
}: ProjectListSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const sectionTitle = `${title} (${count})`;

  const board = (
    <ProjectBoardList
      projects={projects}
      customers={customers}
      users={users}
      streams={streams}
      teams={teams}
      splitActiveHold={splitActiveHold}
      onRowOpen={onRowOpen}
      onEdit={onEdit}
      onArchive={onArchive}
      onDuplicate={onDuplicate}
      onExport={onExport}
      onDelete={onDelete}
      canDelete={canDelete}
    />
  );

  if (!collapsible) {
    return (
      <Box sx={{ mb: nested ? 0.75 : 1, pt: nested ? 0.35 : 0 }}>
        {title.trim() ? (
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: nested ? 600 : 700,
              mb: 0.4,
              fontSize: nested ? '0.72rem' : '0.78rem',
              color: nested ? 'text.secondary' : 'text.primary',
              letterSpacing: nested ? '0.02em' : undefined,
              textTransform: nested ? 'uppercase' : 'none',
            }}
          >
            {sectionTitle}
          </Typography>
        ) : null}
        {projects.length ? (
          board
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ px: 0.5, py: 0.75 }}>
            No projects in this section.
          </Typography>
        )}
      </Box>
    );
  }

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, next) => setExpanded(next)}
      disableGutters
      elevation={0}
      sx={{
        mb: 1,
        border: 1,
        borderColor: 'divider',
        borderRadius: '10px !important',
        '&:before': { display: 'none' },
        overflow: 'hidden',
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 40, px: 1.25, '& .MuiAccordionSummary-content': { my: 0.75 } }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          {sectionTitle}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 1 }}>{board}</AccordionDetails>
    </Accordion>
  );
}
