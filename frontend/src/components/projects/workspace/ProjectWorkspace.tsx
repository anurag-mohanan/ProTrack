import { useMemo } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import FolderRoundedIcon from '@mui/icons-material/FolderRounded';
import FlagRoundedIcon from '@mui/icons-material/FlagRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import { PageContainer } from '../../common/PageContainer';
import { LoadingState } from '../../common/LoadingState';
import { ErrorState } from '../../common/ErrorState';
import { StickyRecordHeader } from '../../ui/design-system';
import { BackButton } from '../../navigation/BackButton';
import { APP_TOP_BAR_OFFSET } from '../../ui/design-system/StickyRecordHeader';
import { commandCenterQueryKeys, fetchProjectCommandCenter } from '../../../api/commandCenter';
import { QuoteAssistantPanel } from '../../ai/QuoteAssistantPanel';
import { ProjectMilestoneGrid } from './ProjectMilestoneGrid';
import { ProjectWorkspaceCompactHeader } from './ProjectWorkspaceCompactHeader';
import { WorkflowTimeline } from '../../command-center/WorkflowTimeline';
import { useAuth } from '../../../context/AuthContext';
import { ROLES } from '../../../utils/permissions';
import { formatDisplayValue } from '../../../utils/format';
import { isActiveProjectForHealth } from '../../../utils/projectHealth';
import { ProjectCommunicationsPanel } from './ProjectCommunicationsPanel';
import { ProjectContributorsPanel } from './ProjectContributorsPanel';
import { ProjectTimesheetsPanel } from './ProjectTimesheetsPanel';
import { getProjectActivities } from '../../../services/notificationService';
import type { Activity } from '../../../types';

const TABS = [
  { id: 'overview', label: 'Overview', icon: FolderRoundedIcon },
  { id: 'milestones', label: 'Milestones', icon: FlagRoundedIcon },
  { id: 'team', label: 'Team', icon: GroupsRoundedIcon },
  { id: 'timesheets', label: 'Timesheets', icon: ScheduleRoundedIcon },
  { id: 'activity', label: 'Activity Log', icon: HistoryRoundedIcon },
  { id: 'communications', label: 'Communications', icon: EmailRoundedIcon },
  { id: 'files', label: 'Files', icon: InsertDriveFileOutlinedIcon },
] as const;

type WorkspaceTab = (typeof TABS)[number]['id'];

function tabFromParam(value: string | null): WorkspaceTab {
  if (value && TABS.some((tab) => tab.id === value)) {
    return value as WorkspaceTab;
  }
  return 'milestones';
}

interface ProjectWorkspaceProps {
  projectId: string;
}

export function ProjectWorkspace({ projectId }: ProjectWorkspaceProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = tabFromParam(searchParams.get('tab'));
  const { user } = useAuth();

  const query = useQuery({
    queryKey: commandCenterQueryKeys.detail(projectId),
    queryFn: () => fetchProjectCommandCenter(projectId),
  });

  const activityQuery = useQuery({
    queryKey: ['activities', 'project', projectId],
    queryFn: () => getProjectActivities(projectId),
    enabled: tab === 'activity',
  });

  const roleName = user?.role_name ?? '';
  const canEditMilestones = (
    [
      ROLES.ADMIN,
      ROLES.ENGINEERING_MANAGER,
      ROLES.PROJECT_MANAGER,
      ROLES.DESIGN_LEADER,
    ] as string[]
  ).includes(roleName);
  const canEditProgress =
    canEditMilestones ||
    (
      [
        ROLES.SENIOR_DESIGNER,
        ROLES.DESIGNER,
        ROLES.JUNIOR_DESIGNER,
        ROLES.SURFACER,
      ] as string[]
    ).includes(roleName);

  const subtitle = useMemo(() => {
    if (!query.data) return '';
    const project = query.data.project;
    return `${formatDisplayValue(project.customer_name)} · ${formatDisplayValue(project.tool_number)}`;
  }, [query.data]);

  if (query.isLoading) return <LoadingState message="Loading project workspace…" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return null;

  const { project, timeline } = query.data;

  return (
    <PageContainer>
      {tab === 'milestones' ? (
        <ProjectWorkspaceCompactHeader project={project} />
      ) : (
        <StickyRecordHeader
          primaryLabel={project.part_description}
          secondaryLabel={subtitle}
          stickyTop={APP_TOP_BAR_OFFSET}
          toolNumber={project.tool_number}
          customerName={project.customer_name}
          executionStatus={project.execution_status}
          dueDate={project.due_date}
          health={
            isActiveProjectForHealth(project.execution_status, project.is_archived)
              ? project.health
              : undefined
          }
          compact
          meta={
            <Typography variant="caption" color="text.secondary">
              Quoted {project.quoted_hours}h
            </Typography>
          }
        />
      )}

      <BackButton fallbackPath="/projects" label="Back to projects" />

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 1.5 }}>
        <Tabs
          value={tab}
          onChange={(_, value: WorkspaceTab) => setSearchParams({ tab: value })}
          variant="scrollable"
          scrollButtons="auto"
        >
          {TABS.map((item) => (
            <Tab key={item.id} value={item.id} label={item.label} />
          ))}
        </Tabs>
      </Box>

      {tab === 'overview' ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              Execution timeline
            </Typography>
            <WorkflowTimeline steps={timeline} />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              Contributors
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Hours logged by each engineer. Assigned designer and surfacer remain project owners
              for planning and milestones.
            </Typography>
            <ProjectContributorsPanel contributors={query.data.contributors ?? []} />
          </Box>
          <QuoteAssistantPanel projectId={projectId} />
        </Box>
      ) : null}

      {tab === 'milestones' ? (
        <ProjectMilestoneGrid
          projectId={projectId}
          canEdit={canEditMilestones}
          canEditProgress={canEditProgress}
        />
      ) : null}

      {tab === 'team' ? (
        <Box sx={{ display: 'grid', gap: 1, maxWidth: 480 }}>
          <Typography variant="body2">Design Leader: {formatDisplayValue(project.design_leader_name)}</Typography>
          <Typography variant="body2">Designer: {formatDisplayValue(project.designer_name)}</Typography>
          <Typography variant="body2">Surfacer: {formatDisplayValue(project.surfacer_name)}</Typography>
          <Typography variant="body2">Team: {formatDisplayValue(project.team_name)}</Typography>
        </Box>
      ) : null}

      {tab === 'timesheets' ? (
        <ProjectTimesheetsPanel projectId={projectId} quotedHours={project.quoted_hours} />
      ) : null}

      {tab === 'activity' ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {(activityQuery.data ?? []).length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No activity recorded yet.
            </Typography>
          ) : (
            (activityQuery.data ?? []).map((entry: Activity) => (
              <Box
                key={entry.id}
                sx={{
                  py: 1,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {entry.action.replaceAll('_', ' ')}
                  {entry.user_name ? ` · ${entry.user_name}` : ''}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {entry.created_at}
                  {entry.old_value || entry.new_value
                    ? ` · ${entry.old_value ?? ''} → ${entry.new_value ?? ''}`
                    : ''}
                </Typography>
              </Box>
            ))
          )}
        </Box>
      ) : null}

      {tab === 'communications' ? <ProjectCommunicationsPanel projectId={projectId} /> : null}

      {tab === 'files' ? (
        <Typography variant="body2" color="text.secondary">
          Engineering documents are stored in the project folder structure configured under System Settings → File Paths.
        </Typography>
      ) : null}
    </PageContainer>
  );
}

export function ProjectWorkspacePage() {
  const { id = '' } = useParams();
  return <ProjectWorkspace projectId={id} />;
}
