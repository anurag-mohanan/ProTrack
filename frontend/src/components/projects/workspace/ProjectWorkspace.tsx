import { useMemo, useState } from 'react';
import { Box, Tab, Tabs, Typography } from '@mui/material';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import FolderRoundedIcon from '@mui/icons-material/FolderRounded';
import FlagRoundedIcon from '@mui/icons-material/FlagRounded';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ArchiveOutlinedIcon from '@mui/icons-material/ArchiveOutlined';
import UnarchiveOutlinedIcon from '@mui/icons-material/UnarchiveOutlined';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { PageContainer } from '../../common/PageContainer';
import { LoadingState } from '../../common/LoadingState';
import { ErrorState } from '../../common/ErrorState';
import { ConfirmDialog } from '../../common/ConfirmDialog';
import { StickyRecordHeader } from '../../ui/design-system';
import { APP_TOP_BAR_OFFSET } from '../../ui/design-system/StickyRecordHeader';
import { commandCenterQueryKeys, fetchProjectCommandCenter } from '../../../api/commandCenter';
import { QuoteAssistantPanel } from '../../ai/QuoteAssistantPanel';
import { ProjectMilestoneGrid } from './ProjectMilestoneGrid';
import { ProjectWorkspaceCompactHeader } from './ProjectWorkspaceCompactHeader';
import { WorkflowTimeline } from '../../command-center/WorkflowTimeline';
import { useAuth } from '../../../context/AuthContext';
import { useToast } from '../../../context/ToastContext';
import {
  accessContextFromUser,
  canArchiveProject,
  canDeleteProject,
  canEditProject,
  ROLES,
} from '../../../utils/permissions';
import { formatDisplayValue } from '../../../utils/format';
import { isActiveProjectForHealth } from '../../../utils/projectHealth';
import { ProjectCommunicationsPanel } from './ProjectCommunicationsPanel';
import { ProjectContributorsPanel } from './ProjectContributorsPanel';
import { ProjectWorkorderDetailsPanel } from './ProjectWorkorderDetailsPanel';
import { ProjectTimesheetsPanel } from './ProjectTimesheetsPanel';
import { ProjectFormDialog } from '../ProjectFormDialog';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { getProjectActivities } from '../../../services/notificationService';
import {
  archiveProject,
  projectQueryKeys,
  restoreProject,
  softDeleteProject,
} from '../../../services/projectService';
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
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = tabFromParam(searchParams.get('tab'));
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const query = useQuery({
    queryKey: commandCenterQueryKeys.detail(projectId),
    queryFn: () => fetchProjectCommandCenter(projectId),
  });

  const activityQuery = useQuery({
    queryKey: ['activities', 'project', projectId],
    queryFn: () => getProjectActivities(projectId),
    enabled: tab === 'activity',
  });

  const access = accessContextFromUser(user);
  const roleName = user?.role_name ?? '';
  const showEditProject = canEditProject(access);
  const showArchive = canArchiveProject(access);
  const showDelete = canDeleteProject(access);
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

  const invalidateProject = () => {
    void queryClient.invalidateQueries({ queryKey: commandCenterQueryKeys.detail(projectId) });
    void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
    void query.refetch();
  };

  const archiveMutation = useMutation({
    mutationFn: () => archiveProject(projectId),
    onSuccess: () => {
      showSuccess('Project archived');
      setArchiveOpen(false);
      invalidateProject();
    },
    onError: (error: Error) => showError(error.message),
  });

  const restoreMutation = useMutation({
    mutationFn: () => restoreProject(projectId),
    onSuccess: () => {
      showSuccess('Project restored to active');
      setRestoreOpen(false);
      invalidateProject();
    },
    onError: (error: Error) => showError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => softDeleteProject(projectId),
    onSuccess: () => {
      showSuccess('Project deleted');
      setDeleteOpen(false);
      void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      navigate('/projects');
    },
    onError: (error: Error) => showError(error.message),
  });

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

      {showEditProject || showArchive || showDelete ? (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 1,
            flexWrap: 'wrap',
            mb: 0.5,
          }}
        >
          {showEditProject ? (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              startIcon={<EditOutlinedIcon />}
              onClick={() => setEditOpen(true)}
            >
              Edit Project
            </ProsohmButton>
          ) : null}
          {showArchive && !project.is_deleted ? (
            project.is_archived ? (
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                startIcon={<UnarchiveOutlinedIcon />}
                onClick={() => setRestoreOpen(true)}
              >
                Restore
              </ProsohmButton>
            ) : (
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                startIcon={<ArchiveOutlinedIcon />}
                onClick={() => setArchiveOpen(true)}
              >
                Archive
              </ProsohmButton>
            )
          ) : null}
          {showDelete && !project.is_deleted ? (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              startIcon={<DeleteOutlineRoundedIcon />}
              onClick={() => setDeleteOpen(true)}
              sx={{ color: 'error.main', borderColor: 'error.main' }}
            >
              Delete
            </ProsohmButton>
          ) : null}
        </Box>
      ) : null}

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
          <ProjectWorkorderDetailsPanel project={project} canEdit={canEditMilestones} />
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
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, maxWidth: 720 }}>
          <Typography variant="body2" color="text.secondary">
            Engineering documents stay in the project folder structure configured under System
            Settings → File Paths. Capture workorder attributes on Overview so they remain searchable
            after the tool is completed.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Use Overview → Import workorder PDF to autofill tonnage, material, and related fields from a
            text-based customer PDF (review before Save). Per-customer template fine-tuning remains a later
            enhancement for difficult layouts.
          </Typography>
        </Box>
      ) : null}

      <ProjectFormDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        project={project}
        onUpdated={() => {
          setEditOpen(false);
          invalidateProject();
        }}
      />

      <ConfirmDialog
        open={archiveOpen}
        title="Archive project?"
        message="Archived projects are removed from the default list but remain in reports and history."
        confirmLabel="Archive"
        danger
        loading={archiveMutation.isPending}
        onClose={() => setArchiveOpen(false)}
        onConfirm={() => archiveMutation.mutate()}
      />

      <ConfirmDialog
        open={restoreOpen}
        title="Restore project?"
        message="The project will return to Active Projects as Currently Being Worked On."
        confirmLabel="Restore"
        loading={restoreMutation.isPending}
        onClose={() => setRestoreOpen(false)}
        onConfirm={() => restoreMutation.mutate()}
      />

      <ConfirmDialog
        open={deleteOpen}
        title="Delete project?"
        message={
          Number(project.actual_hours) > 0
            ? `This removes ${project.tool_number} from active project management. Timesheets, milestones, and post-completion hours are kept for history. Restore from Deleted Projects if needed.`
            : 'This removes the project from active project management. Related timesheets, milestones, and history are kept. The project can be restored from Deleted Projects.'
        }
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
      />
    </PageContainer>
  );
}

export function ProjectWorkspacePage() {
  const { id = '' } = useParams();
  return <ProjectWorkspace projectId={id} />;
}
