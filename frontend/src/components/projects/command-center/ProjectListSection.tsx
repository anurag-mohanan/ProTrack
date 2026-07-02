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
import { ContentCard } from '../../ui/cards';
import { ProjectTable, type ProjectTableRow } from '../ProjectTable';

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
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
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
  onRowOpen,
  onEdit,
  onArchive,
}: ProjectListSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const sectionTitle = `${title} (${count})`;

  const table = (
    <Box sx={{ borderRadius: 3, overflow: 'hidden' }}>
      <ContentCard noPadding>
        <ProjectTable
        projects={projects}
        customers={customers}
        users={users}
        streams={streams}
        teams={teams}
        onRowOpen={onRowOpen}
        onEdit={onEdit}
        onArchive={onArchive}
        compact
      />
      </ContentCard>
    </Box>
  );

  if (!collapsible) {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
          {sectionTitle}
        </Typography>
        {table}
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
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          {sectionTitle}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 0 }}>{table}</AccordionDetails>
    </Accordion>
  );
}
