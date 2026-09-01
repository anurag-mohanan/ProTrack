import { useState } from 'react';
import { Box, Chip, Collapse, IconButton, Stack, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { Customer, Stream, Team, User } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { ProjectListSection } from './ProjectListSection';
import { ProjectStreamPanel } from './ProjectStreamPanel';
import type { ProjectTableRow } from '../ProjectTable';
import type { ProjectTeamStreamSection } from '../../../utils/projectTeamStreamHierarchy';
import { sortCompletedProjects, sortLiveProjects } from '../../../utils/projectCommandCenter';

interface ProjectTeamCommandCenterProps {
  sections: ProjectTeamStreamSection[];
  customers: Customer[];
  users: User[];
  streams: Stream[];
  teams: Team[];
  gridSessionKey?: number;
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onDuplicate?: (projectId: string) => void;
  onExport?: (row: ProjectTableRow) => void;
  onDelete?: (projectId: string) => void;
  canDelete?: boolean;
}

function TeamKpiLine({ section }: { section: ProjectTeamStreamSection }) {
  const parts = [
    section.activeCount ? `${section.activeCount} Active` : null,
    section.completedCount ? `${section.completedCount} Completed` : null,
    section.overdueCount ? `${section.overdueCount} Overdue` : null,
    section.fullDesignCount ? `${section.fullDesignCount} Full Design` : null,
    section.smallTaskCount ? `${section.smallTaskCount} Small Tasks` : null,
  ].filter(Boolean);

  if (!parts.length) return null;

  return (
    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
      {parts.join(' · ')}
    </Typography>
  );
}

function StreamKpiLine({ active, completed }: { active: number; completed: number }) {
  const parts = [
    active ? `${active} Active` : null,
    completed ? `${completed} Completed` : null,
  ].filter(Boolean);
  if (!parts.length) return null;
  return (
    <Typography
      variant="caption"
      color="text.secondary"
      sx={{ fontWeight: 600, display: 'block', mt: 0.15 }}
    >
      {parts.join(' · ')}
    </Typography>
  );
}

function TeamPanel({
  section,
  children,
  defaultExpanded = true,
}: {
  section: ProjectTeamStreamSection;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const total = section.activeCount + section.completedCount;

  return (
    <Box
      sx={{
        mb: 2,
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
          alignItems: 'flex-start',
          gap: 1,
          px: 1.5,
          py: 1.1,
          m: 0,
          border: 0,
          cursor: 'pointer',
          textAlign: 'left',
          bgcolor: 'transparent',
          borderLeft: `4px solid ${designTokens.semantic.primary}`,
          '&:hover': { bgcolor: designTokens.semantic.neutralSoft },
        }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 800, letterSpacing: '-0.01em', lineHeight: 1.25 }}
          >
            {section.teamName}
          </Typography>
          <TeamKpiLine section={section} />
        </Box>
        <Chip
          size="small"
          label={total}
          sx={{
            height: 22,
            fontWeight: 700,
            fontSize: '0.72rem',
            bgcolor: designTokens.semantic.primarySoft,
            color: designTokens.semantic.primary,
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
            px: 1.25,
            pb: 1.25,
            pt: 0.5,
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

export function ProjectTeamCommandCenter({
  sections,
  customers,
  users,
  streams,
  teams,
  gridSessionKey,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  canDelete,
}: ProjectTeamCommandCenterProps) {
  const listProps = {
    customers,
    users,
    streams,
    teams,
    gridSessionKey,
    onRowOpen,
    onEdit,
    onArchive,
    onDuplicate,
    onExport,
    onDelete,
    canDelete,
  };

  if (!sections.length) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No projects match the current filters.
      </Typography>
    );
  }

  return (
    <Stack spacing={0}>
      {sections.map((teamSection) => (
        <TeamPanel key={teamSection.teamId ?? 'unassigned'} section={teamSection}>
          {teamSection.streams.map((streamSection) => (
            <ProjectStreamPanel
              key={`${teamSection.teamId ?? 'unassigned'}-${streamSection.streamId ?? 'unassigned'}`}
              streamName={streamSection.streamName}
              projectCount={streamSection.activeCount + streamSection.completedCount}
              defaultExpanded
              showChrome
            >
              <StreamKpiLine
                active={streamSection.activeCount}
                completed={streamSection.completedCount}
              />
              {streamSection.activeCount > 0 ? (
                <ProjectListSection
                  title="Active Projects"
                  count={streamSection.activeCount}
                  projects={sortLiveProjects(streamSection.activeProjects)}
                  nested
                  primary
                  {...listProps}
                />
              ) : null}
              {streamSection.completedCount > 0 ? (
                <ProjectListSection
                  title="Completed Projects"
                  count={streamSection.completedCount}
                  projects={sortCompletedProjects(streamSection.completedProjects)}
                  nested
                  collapsible
                  defaultExpanded={false}
                  splitActiveHold={false}
                  {...listProps}
                />
              ) : null}
            </ProjectStreamPanel>
          ))}
        </TeamPanel>
      ))}
    </Stack>
  );
}
