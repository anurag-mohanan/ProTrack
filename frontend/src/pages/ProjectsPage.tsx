import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchCustomers, fetchStreams, fetchTeams, fetchUsers } from '../api/lookups';
import { fetchProjectTypes } from '../api/projectTemplates';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectRecordDrawer } from '../components/projects/ProjectRecordDrawer';
import {
  ProjectFiltersBar,
  type ProjectFilterValues,
} from '../components/projects/ProjectFiltersBar';
import { ProjectTable, type ProjectTableRow } from '../components/projects/ProjectTable';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageHeader } from '../components/common/PageHeader';
import { PageContainer } from '../components/common/PageContainer';
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
import { canArchiveProject } from '../utils/permissions';

const lifecycleOptions: Array<{ value: ProjectLifecycleFilter; label: string }> = [
  { value: 'all', label: 'All Projects' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'archived', label: 'Archived' },
  { value: 'deleted', label: 'Deleted' },
];

const defaultFilters: ProjectFilterValues = {
  customerIds: [],
  projectTypeId: 'all',
  teamIds: [],
  projectStage: 'all',
  executionStatus: 'all',
  designLeaderId: 'all',
  designerId: 'all',
  surfacerId: 'all',
};

export function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [filterValues, setFilterValues] = useState<ProjectFilterValues>(defaultFilters);
  const [groupByTeam, setGroupByTeam] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editProject, setEditProject] = useState<ProjectTableRow | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectTableRow | null>(null);
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);

  const lifecycle =
    (searchParams.get('lifecycle') as ProjectLifecycleFilter | null) ?? 'all';
  const dueFilter = searchParams.get('due');
  const completedFilter = searchParams.get('completed');

  useEffect(() => {
    const executionStatus = searchParams.get('execution_status');
    if (executionStatus) {
      setFilterValues((current) => ({
        ...current,
        executionStatus: executionStatus as ExecutionStatus,
      }));
    }

    const projectStage = searchParams.get('project_stage');
    if (projectStage) {
      setFilterValues((current) => ({
        ...current,
        projectStage: projectStage as ProjectStage,
      }));
    }

    const teamId = searchParams.get('team_id');
    if (teamId) {
      setFilterValues((current) => ({
        ...current,
        teamIds: [teamId],
      }));
    }

    const customerId = searchParams.get('customer_id');
    if (customerId) {
      setFilterValues((current) => ({
        ...current,
        customerIds: [customerId],
      }));
    }
  }, [searchParams]);

  const listParams = useMemo(
    () => ({
      lifecycle,
      execution_status:
        filterValues.executionStatus === 'all'
          ? undefined
          : filterValues.executionStatus,
      project_stage:
        filterValues.projectStage === 'all' ? undefined : filterValues.projectStage,
      customer_ids:
        filterValues.customerIds.length > 0 ? filterValues.customerIds : undefined,
      team_ids: filterValues.teamIds.length > 0 ? filterValues.teamIds : undefined,
      project_type_id:
        filterValues.projectTypeId === 'all' ? undefined : filterValues.projectTypeId,
      design_leader_id:
        filterValues.designLeaderId === 'all' ? undefined : filterValues.designLeaderId,
      designer_id:
        filterValues.designerId === 'all' ? undefined : filterValues.designerId,
      surfacer_id:
        filterValues.surfacerId === 'all' ? undefined : filterValues.surfacerId,
      limit: 500,
    }),
    [lifecycle, filterValues],
  );

  const projectsQuery = useQuery({
    queryKey: projectQueryKeys.list(listParams),
    queryFn: () => getProjects(listParams),
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

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const projectTypesQuery = useQuery({
    queryKey: ['project-types'],
    queryFn: fetchProjectTypes,
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

  const sortedProjects = useMemo(() => {
    const rows = filteredProjects;
    if (!groupByTeam) return rows;
    const teamMap = new Map((teamsQuery.data ?? []).map((team) => [team.id, team.name]));
    return [...rows].sort((a, b) => {
      const teamA = a.team_id ? (teamMap.get(a.team_id) ?? 'Unassigned') : 'Unassigned';
      const teamB = b.team_id ? (teamMap.get(b.team_id) ?? 'Unassigned') : 'Unassigned';
      return teamA.localeCompare(teamB) || a.tool_number.localeCompare(b.tool_number);
    });
  }, [filteredProjects, groupByTeam, teamsQuery.data]);

  const tableLoading = projectsQuery.isPending;

  const lookupLoadIssues = [
    customersQuery.error ? 'customers' : null,
    usersQuery.error ? 'users' : null,
    streamsQuery.error ? 'streams' : null,
    teamsQuery.error ? 'teams' : null,
    projectTypesQuery.error ? 'project types' : null,
  ].filter((value): value is string => value !== null);

  const showArchiveActions =
    lifecycle !== 'archived' &&
    lifecycle !== 'deleted' &&
    canArchiveProject(user?.role_name ?? '');

  const showRestoreActions = lifecycle === 'cancelled';

  const lifecycleSubtitle: Record<ProjectLifecycleFilter, string> = {
    all: 'Browse all projects including active, completed, and archived',
    active: 'Manage engineering projects and assignments',
    completed: 'Review completed projects and delivery history',
    cancelled: 'Cancelled projects are excluded from workload and active KPIs',
    archived: 'Browse archived projects with full history preserved',
    deleted: 'Soft-deleted projects — permanent deletion requires admin approval',
  };

  if (projectsQuery.error) {
    return <ErrorState error={projectsQuery.error} title="Unable to load projects" />;
  }

  return (
    <PageContainer>
      {lookupLoadIssues.length > 0 ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Some filter options could not be loaded ({lookupLoadIssues.join(', ')}). Project
          data is still shown below.
        </Alert>
      ) : null}
      <PageHeader
        title={
          lifecycle === 'all'
            ? 'All Projects'
            : lifecycle === 'cancelled'
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
          lifecycle === 'active' || lifecycle === 'all' ? (
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
              if (value === 'all') {
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
        <FormControlLabel
          control={
            <Switch
              checked={groupByTeam}
              onChange={(event) => setGroupByTeam(event.target.checked)}
            />
          }
          label="Group by Team"
        />
      </SearchToolbar>

      <Box sx={{ mb: 2.5 }}>
        <ContentCard>
          <ProjectFiltersBar
            customers={customersQuery.data ?? []}
            teams={teamsQuery.data ?? []}
            projectTypes={projectTypesQuery.data ?? []}
            users={usersQuery.data ?? []}
            values={filterValues}
            onChange={setFilterValues}
          />
        </ContentCard>
      </Box>

      {tableLoading ? (
        <ContentCard noPadding>
          <TableSkeleton rows={10} columns={8} />
        </ContentCard>
      ) : !sortedProjects.length ? (
        <EmptyState
          title="No projects found"
          description="Try adjusting your search or filters, or create a new project."
        />
      ) : (
        <ContentCard noPadding>
          <ProjectTable
            projects={sortedProjects}
            customers={customersQuery.data ?? []}
            users={usersQuery.data ?? []}
            streams={streamsQuery.data ?? []}
            teams={teamsQuery.data ?? []}
            onRowOpen={setSelectedProject}
            onEdit={setEditProject}
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
        onCreated={() => {
          setCreateOpen(false);
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
        }}
      />

      <ProjectFormDialog
        open={Boolean(editProject)}
        onClose={() => setEditProject(null)}
        project={editProject ?? undefined}
        onUpdated={() => {
          setEditProject(null);
          setSelectedProject(null);
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
        }}
      />

      <ProjectRecordDrawer
        project={selectedProject}
        open={Boolean(selectedProject)}
        onClose={() => setSelectedProject(null)}
        onEdit={(project) => {
          setEditProject(project);
          setSelectedProject(null);
        }}
        onArchive={(projectId) => setArchiveId(projectId)}
        canArchive={showArchiveActions}
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
    </PageContainer>
  );
}
