import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchCustomers, fetchStreams, fetchUsers } from '../api/lookups';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectTable } from '../components/projects/ProjectTable';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageHeader } from '../components/common/PageHeader';
import { TableSkeleton } from '../components/common/TableSkeleton';
import { SearchToolbar } from '../components/ui/design-system';
import { ContentCard } from '../components/ui/cards';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  archiveProject,
  getProjects,
  projectQueryKeys,
  updateProject,
} from '../services/projectService';
import type { ExecutionStatus, ProjectLifecycleFilter, ProjectStage } from '../types';
import {
  EXECUTION_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
} from '../types/common';
import { canArchiveProject } from '../utils/permissions';

const lifecycleOptions: Array<{ value: ProjectLifecycleFilter; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'archived', label: 'Archived' },
  { value: 'deleted', label: 'Deleted' },
];

const executionStatusOptions: Array<{ value: ExecutionStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All Execution Statuses' },
  ...(
    Object.entries(EXECUTION_STATUS_LABELS) as Array<[ExecutionStatus, string]>
  ).map(([value, label]) => ({ value, label })),
];

const projectStageOptions: Array<{ value: ProjectStage | 'all'; label: string }> = [
  { value: 'all', label: 'All Stages' },
  ...(
    Object.entries(PROJECT_STAGE_LABELS) as Array<[ProjectStage, string]>
  ).map(([value, label]) => ({ value, label })),
];

export function ProjectsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [executionStatusFilter, setExecutionStatusFilter] = useState<
    ExecutionStatus | 'all'
  >('all');
  const [projectStageFilter, setProjectStageFilter] = useState<ProjectStage | 'all'>(
    'all',
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);

  const lifecycle =
    (searchParams.get('lifecycle') as ProjectLifecycleFilter | null) ?? 'active';
  const dueFilter = searchParams.get('due');
  const completedFilter = searchParams.get('completed');

  useEffect(() => {
    const executionStatus = searchParams.get('execution_status');
    if (
      executionStatus &&
      executionStatusOptions.some((option) => option.value === executionStatus)
    ) {
      setExecutionStatusFilter(executionStatus as ExecutionStatus);
    } else if (!executionStatus) {
      setExecutionStatusFilter('all');
    }

    const projectStage = searchParams.get('project_stage');
    if (
      projectStage &&
      projectStageOptions.some((option) => option.value === projectStage)
    ) {
      setProjectStageFilter(projectStage as ProjectStage);
    } else if (!projectStage) {
      setProjectStageFilter('all');
    }
  }, [searchParams]);

  const executionStatusParam =
    executionStatusFilter === 'all' ? undefined : executionStatusFilter;
  const projectStageParam =
    projectStageFilter === 'all' ? undefined : projectStageFilter;

  const projectsQuery = useQuery({
    queryKey: projectQueryKeys.list({
      lifecycle,
      execution_status: executionStatusParam,
      project_stage: projectStageParam,
    }),
    queryFn: () =>
      getProjects({
        lifecycle,
        execution_status: executionStatusParam,
        project_stage: projectStageParam,
        limit: 500,
      }),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const archiveMutation = useMutation({
    mutationFn: archiveProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project archived');
      setArchiveId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const restoreMutation = useMutation({
    mutationFn: (projectId: string) =>
      updateProject(projectId, {
        execution_status: 'currently_being_worked_on',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project restored to active');
      setRestoreId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: fetchUsers,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const streamsQuery = useQuery({
    queryKey: ['lookups', 'streams'],
    queryFn: fetchStreams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const filteredProjects = useMemo(() => {
    let rows = projectsQuery.data ?? [];
    const term = search.trim().toLowerCase();
    if (term) {
      rows = rows.filter((project) => {
        const haystack = [project.tool_number, project.part_description]
          .join(' ')
          .toLowerCase();
        return haystack.includes(term);
      });
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (dueFilter === 'week' || dueFilter === '7days') {
      const rangeStart = new Date(today);
      if (dueFilter === 'week') {
        const day = rangeStart.getDay();
        const diff = day === 0 ? -6 : 1 - day;
        rangeStart.setDate(rangeStart.getDate() + diff);
      }
      const rangeEnd = new Date(rangeStart);
      rangeEnd.setDate(
        rangeEnd.getDate() + (dueFilter === 'week' ? 6 : 7),
      );

      rows = rows.filter((project) => {
        if (!project.due_date || project.execution_status === 'completed') return false;
        const due = new Date(`${project.due_date}T00:00:00`);
        return due >= rangeStart && due <= rangeEnd;
      });
    }

    if (dueFilter === 'overdue') {
      rows = rows.filter((project) => {
        if (!project.due_date || project.execution_status === 'completed') return false;
        return new Date(`${project.due_date}T00:00:00`) < today;
      });
    }

    if (completedFilter === 'month') {
      const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
      rows = rows.filter((project) => {
        if (project.execution_status !== 'completed' || !project.completed_at) return false;
        const completed = new Date(project.completed_at);
        return completed >= monthStart && completed <= today;
      });
    }

    return rows;
  }, [projectsQuery.data, search, dueFilter, completedFilter]);

  const tableLoading =
    projectsQuery.isPending ||
    customersQuery.isPending ||
    usersQuery.isPending ||
    streamsQuery.isPending;

  const showArchiveActions =
    lifecycle !== 'archived' &&
    lifecycle !== 'deleted' &&
    canArchiveProject(user?.role_name ?? '');

  const showRestoreActions = lifecycle === 'cancelled';

  const lifecycleSubtitle: Record<ProjectLifecycleFilter, string> = {
    active: 'Manage engineering projects and assignments',
    completed: 'Review completed projects and delivery history',
    cancelled: 'Cancelled projects are excluded from workload and active KPIs',
    archived: 'Browse archived projects with full history preserved',
    deleted: 'Soft-deleted projects — permanent deletion requires admin approval',
  };

  if (projectsQuery.error) return <ErrorState error={projectsQuery.error} />;
  if (customersQuery.error) return <ErrorState error={customersQuery.error} />;
  if (usersQuery.error) return <ErrorState error={usersQuery.error} />;
  if (streamsQuery.error) return <ErrorState error={streamsQuery.error} />;

  return (
    <Box>
      <PageHeader
        title={
          lifecycle === 'cancelled'
            ? 'Cancelled Projects'
            : lifecycle === 'completed'
              ? 'Completed Projects'
              : lifecycle === 'archived'
                ? 'Archived Projects'
                : lifecycle === 'deleted'
                  ? 'Deleted Projects'
                  : 'Projects'
        }
        subtitle={lifecycleSubtitle[lifecycle]}
        action={
          lifecycle === 'active' ? (
            <ProsohmButton
              buttonVariant="primary"
              startIcon={<AddIcon />}
              onClick={() => setCreateOpen(true)}
            >
              Create Project
            </ProsohmButton>
          ) : undefined
        }
      />

      <SearchToolbar>
            <TextField
              label="Search tool number or description"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              sx={{ minWidth: 280, flex: 1 }}
            />
            <FormControl sx={{ minWidth: 180 }}>
              <InputLabel>Lifecycle</InputLabel>
              <Select
                label="Lifecycle"
                value={lifecycle}
                onChange={(event) => {
                  const value = event.target.value as ProjectLifecycleFilter;
                  const next = new URLSearchParams(searchParams);
                  if (value === 'active') {
                    next.delete('lifecycle');
                  } else {
                    next.set('lifecycle', value);
                  }
                  setSearchParams(next);
                }}
              >
                {lifecycleOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl sx={{ minWidth: 220 }}>
              <InputLabel>Project Stage</InputLabel>
              <Select
                label="Project Stage"
                value={projectStageFilter}
                onChange={(event) => {
                  const value = event.target.value as ProjectStage | 'all';
                  setProjectStageFilter(value);
                  const next = new URLSearchParams(searchParams);
                  if (value === 'all') {
                    next.delete('project_stage');
                  } else {
                    next.set('project_stage', value);
                  }
                  setSearchParams(next);
                }}
              >
                {projectStageOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl sx={{ minWidth: 240 }}>
              <InputLabel>Execution Status</InputLabel>
              <Select
                label="Execution Status"
                value={executionStatusFilter}
                onChange={(event) => {
                  const value = event.target.value as ExecutionStatus | 'all';
                  setExecutionStatusFilter(value);
                  const next = new URLSearchParams(searchParams);
                  if (value === 'all') {
                    next.delete('execution_status');
                  } else {
                    next.set('execution_status', value);
                  }
                  setSearchParams(next);
                }}
              >
                {executionStatusOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
      </SearchToolbar>

      {tableLoading ? (
        <ContentCard noPadding>
          <TableSkeleton rows={10} columns={8} />
        </ContentCard>
      ) : !filteredProjects.length ? (
        <EmptyState
          title="No projects found"
          description="Try adjusting your search or filters, or create a new project."
        />
      ) : (
        <ContentCard noPadding>
          <ProjectTable
            projects={filteredProjects}
            customers={customersQuery.data ?? []}
            users={usersQuery.data ?? []}
            streams={streamsQuery.data ?? []}
            onArchive={
              showArchiveActions ? (projectId) => setArchiveId(projectId) : undefined
            }
            onRestore={
              showRestoreActions ? (projectId) => setRestoreId(projectId) : undefined
            }
          />
        </ContentCard>
      )}

      <ProjectFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(projectId) => navigate(`/projects/${projectId}`)}
      />

      <ConfirmDialog
        open={restoreId !== null}
        title="Restore project?"
        message="The project will return to Active Projects as Currently Being Worked On."
        confirmLabel="Restore"
        loading={restoreMutation.isPending}
        onClose={() => setRestoreId(null)}
        onConfirm={() => restoreId && restoreMutation.mutate(restoreId)}
      />

      <ConfirmDialog
        open={archiveId !== null}
        title="Archive project?"
        message="Archived projects are removed from the default list but remain in reports and history."
        confirmLabel="Archive"
        loading={archiveMutation.isPending}
        onClose={() => setArchiveId(null)}
        onConfirm={() => archiveId && archiveMutation.mutate(archiveId)}
      />
    </Box>
  );
}
