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
      <Box sx={{ mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.75 }}>
          {sectionTitle}
        </Typography>
        {projects.length ? (
          board
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ px: 0.5, py: 1 }}>
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
        mb: 2,
        border: 1,
        borderColor: 'divider',
        borderRadius: '12px !important',
        '&:before': { display: 'none' },
        overflow: 'hidden',
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 48 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          {sectionTitle}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 1.5 }}>{board}</AccordionDetails>
    </Accordion>
  );
}
