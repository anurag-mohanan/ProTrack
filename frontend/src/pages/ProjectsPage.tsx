import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, TextField, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchCustomers, fetchStreams, fetchTeams, fetchUsers } from '../api/lookups';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { fetchProjectTypes } from '../api/projectTemplates';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageHeader } from '../components/common/PageHeader';
import { PageContainer } from '../components/common/PageContainer';
import { TableSkeleton } from '../components/common/TableSkeleton';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectRecordDrawer } from '../components/projects/ProjectRecordDrawer';
import type { ProjectTableRow } from '../components/projects/ProjectTable';
import { ProjectCustomerWorkloadStrip } from '../components/projects/command-center/ProjectCustomerWorkloadStrip';
import { ProjectDesignerAvailabilityStrip } from '../components/projects/command-center/ProjectDesignerAvailabilityStrip';
import { ProjectFilterSidebar } from '../components/projects/command-center/ProjectFilterSidebar';
import { ProjectKpiBar } from '../components/projects/command-center/ProjectKpiBar';
import { ProjectListSection } from '../components/projects/command-center/ProjectListSection';
import { ProjectQuickFilterStrip } from '../components/projects/command-center/ProjectQuickFilterStrip';
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
import type { ExecutionStatus, ProjectStage } from '../types';
import { canArchiveProject } from '../utils/permissions';
import {
  countByExecutionStatus,
  countDueThisWeekProjects,
  countNotStartedProjects,
  countOverdueProjects,
  defaultProjectCommandCenterFilters,
  filterProjectsForCommandCenter,
  isArchivedProject,
  isCompletedProject,
  isLiveProject,
  sortCompletedProjects,
  sortLiveProjects,
  sortProjectsByTeam,
  type ProjectCommandCenterFilters,
  type ProjectQuickFilter,
} from '../utils/projectCommandCenter';

export function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [draftFilters, setDraftFilters] = useState<ProjectCommandCenterFilters>(
    defaultProjectCommandCenterFilters,
  );
  const [appliedFilters, setAppliedFilters] = useState<ProjectCommandCenterFilters>(
    defaultProjectCommandCenterFilters,
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [editProject, setEditProject] = useState<ProjectTableRow | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectTableRow | null>(null);
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);

  useEffect(() => {
    const executionStatus = searchParams.get('execution_status');
    const projectStage = searchParams.get('project_stage');
    const teamId = searchParams.get('team_id');
    const customerId = searchParams.get('customer_id');
    const due = searchParams.get('due');
    const completed = searchParams.get('completed');
    const lifecycle = searchParams.get('lifecycle');

    if (
      !executionStatus &&
      !projectStage &&
      !teamId &&
      !customerId &&
      !due &&
      !completed &&
      !lifecycle
    ) {
      return;
    }

    setDraftFilters((current) => ({
      ...current,
      executionStatus: (executionStatus as ExecutionStatus) || current.executionStatus,
      projectStage: (projectStage as ProjectStage) || current.projectStage,
      teamIds: teamId ? [teamId] : current.teamIds,
      customerIds: customerId ? [customerId] : current.customerIds,
      customerId: customerId ?? current.customerId,
      dueDate:
        due === 'overdue'
          ? 'overdue'
          : due === 'week' || due === '7days'
            ? due
            : current.dueDate,
      quickFilter:
        lifecycle === 'archived'
          ? 'archived'
          : completed === 'month'
            ? 'completed_month'
            : due === 'overdue'
              ? 'overdue'
              : due === 'week' || due === '7days'
                ? 'due_week'
                : executionStatus === 'currently_being_worked_on'
                  ? 'in_progress'
                  : executionStatus === 'on_hold'
                    ? 'on_hold'
                    : current.quickFilter,
      showArchived: lifecycle === 'archived' ? true : current.showArchived,
    }));
    setAppliedFilters((current) => ({
      ...current,
      executionStatus: (executionStatus as ExecutionStatus) || current.executionStatus,
      projectStage: (projectStage as ProjectStage) || current.projectStage,
      teamIds: teamId ? [teamId] : current.teamIds,
      customerIds: customerId ? [customerId] : current.customerIds,
      customerId: customerId ?? current.customerId,
      dueDate:
        due === 'overdue'
          ? 'overdue'
          : due === 'week' || due === '7days'
            ? due
            : current.dueDate,
      quickFilter:
        lifecycle === 'archived'
          ? 'archived'
          : completed === 'month'
            ? 'completed_month'
            : due === 'overdue'
              ? 'overdue'
              : due === 'week' || due === '7days'
                ? 'due_week'
                : executionStatus === 'currently_being_worked_on'
                  ? 'in_progress'
                  : executionStatus === 'on_hold'
                    ? 'on_hold'
                    : current.quickFilter,
      showArchived: lifecycle === 'archived' ? true : current.showArchived,
    }));
  }, [searchParams]);

  const listParams = useMemo(
    () => ({
      execution_status:
        appliedFilters.executionStatus === 'all'
          ? undefined
          : appliedFilters.executionStatus,
      project_stage:
        appliedFilters.projectStage === 'all' ? undefined : appliedFilters.projectStage,
      customer_ids:
        appliedFilters.customerIds.length > 0 ? appliedFilters.customerIds : undefined,
      team_ids: appliedFilters.teamIds.length > 0 ? appliedFilters.teamIds : undefined,
      project_type_id:
        appliedFilters.projectTypeId === 'all' ? undefined : appliedFilters.projectTypeId,
      design_leader_id:
        appliedFilters.designLeaderId === 'all' ? undefined : appliedFilters.designLeaderId,
      designer_id:
        appliedFilters.designerId === 'all' ? undefined : appliedFilters.designerId,
      surfacer_id:
        appliedFilters.surfacerId === 'all' ? undefined : appliedFilters.surfacerId,
      limit: 500,
    }),
    [appliedFilters],
  );

  const projectsQuery = useQuery({
    queryKey: projectQueryKeys.list(listParams),
    queryFn: () => getProjects(listParams),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const dashboardQuery = useQuery({
    queryKey: dashboardQueryKeys.summary(undefined, undefined),
    queryFn: () => fetchDashboardSummary(),
    staleTime: QUERY_STALE_TIMES.dashboard,
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

  const archiveMutation = useMutation({
    mutationFn: archiveProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.all });
      showSuccess('Project archived');
      setArchiveId(null);
      setSelectedProject(null);
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

  const lookup = useMemo(
    () => ({
      customers: customersQuery.data ?? [],
      teams: teamsQuery.data ?? [],
      users: usersQuery.data ?? [],
    }),
    [customersQuery.data, teamsQuery.data, usersQuery.data],
  );

  const filteredProjects = useMemo(() => {
    return filterProjectsForCommandCenter(projectsQuery.data ?? [], appliedFilters, lookup);
  }, [appliedFilters, lookup, projectsQuery.data]);

  const liveProjects = useMemo(() => {
    const live = filteredProjects.filter(isLiveProject);
    const sorted = sortLiveProjects(live);
    return appliedFilters.groupByTeam
      ? sortProjectsByTeam(sorted, teamsQuery.data ?? [])
      : sorted;
  }, [appliedFilters.groupByTeam, filteredProjects, teamsQuery.data]);

  const completedProjects = useMemo(() => {
    const completed = filteredProjects.filter(isCompletedProject);
    const sorted = sortCompletedProjects(completed);
    return appliedFilters.groupByTeam
      ? sortProjectsByTeam(sorted, teamsQuery.data ?? [])
      : sorted;
  }, [appliedFilters.groupByTeam, filteredProjects, teamsQuery.data]);

  const archivedProjects = useMemo(
    () => filteredProjects.filter(isArchivedProject),
    [filteredProjects],
  );

  const displayLiveProjects = appliedFilters.showArchived || appliedFilters.quickFilter === 'archived'
    ? archivedProjects
    : liveProjects;

  const allProjectsForCounts = projectsQuery.data ?? [];
  const quickCounts = useMemo(
    () => ({
      inProgress: countByExecutionStatus(allProjectsForCounts, 'currently_being_worked_on'),
      onHold: countByExecutionStatus(allProjectsForCounts, 'on_hold'),
      overdue: countOverdueProjects(allProjectsForCounts),
      dueWeek: countDueThisWeekProjects(allProjectsForCounts),
      notStarted: countNotStartedProjects(allProjectsForCounts),
    }),
    [allProjectsForCounts],
  );

  const applyFilters = useCallback(() => {
    setAppliedFilters({
      ...draftFilters,
      customerId: draftFilters.customerIds.length === 1 ? draftFilters.customerIds[0] : draftFilters.customerId,
    });
    setSearchParams({});
  }, [draftFilters, setSearchParams]);

  const clearFilters = useCallback(() => {
    setDraftFilters(defaultProjectCommandCenterFilters);
    setAppliedFilters(defaultProjectCommandCenterFilters);
    setSearchParams({});
  }, [setSearchParams]);

  const handleQuickFilter = useCallback((filter: ProjectQuickFilter) => {
    setAppliedFilters((current) => ({
      ...current,
      quickFilter: filter,
      showArchived: filter === 'archived',
      dueDate:
        filter === 'overdue'
          ? 'overdue'
          : filter === 'due_week'
            ? 'week'
            : filter === 'none'
              ? 'all'
              : current.dueDate,
    }));
    setDraftFilters((current) => ({
      ...current,
      quickFilter: filter,
      showArchived: filter === 'archived',
    }));
    setSearchParams({});
  }, [setSearchParams]);

  const handleCustomerSelect = useCallback((customerId: string | undefined) => {
    setAppliedFilters((current) => ({
      ...current,
      customerId,
      customerIds: customerId ? [customerId] : [],
      quickFilter: 'none',
    }));
    setDraftFilters((current) => ({
      ...current,
      customerId,
      customerIds: customerId ? [customerId] : [],
    }));
  }, []);

  const handleDesignerSelect = useCallback((designerUserId: string | undefined) => {
    setAppliedFilters((current) => ({
      ...current,
      designerUserId,
      designerId: designerUserId ?? 'all',
      quickFilter: 'none',
    }));
    setDraftFilters((current) => ({
      ...current,
      designerUserId,
      designerId: designerUserId ?? 'all',
    }));
  }, []);

  const showArchiveActions = canArchiveProject(user?.role_name ?? '');
  const tableLoading = projectsQuery.isPending;
  const summary = dashboardQuery.data;
  const liveCount = displayLiveProjects.length;
  const completedCount = completedProjects.length;

  if (projectsQuery.error) {
    return <ErrorState error={projectsQuery.error} title="Unable to load projects" />;
  }

  return (
    <PageContainer>
      <PageHeader
        title="Project Command Center"
        subtitle={
          summary
            ? `${summary.active_projects} active · ${summary.overdue_projects} overdue · ${summary.projects_due_this_week} due this week`
            : 'Operational hub for live engineering projects'
        }
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
            Create Project
          </ProsohmButton>
        }
      />

      <Box sx={{ mb: 2, maxWidth: 480 }}>
        <TextField
          fullWidth
          label="Search projects"
          placeholder="Tool number, customer, designer, team, description…"
          value={appliedFilters.search}
          onChange={(event) => {
            const search = event.target.value;
            setAppliedFilters((current) => ({ ...current, search }));
            setDraftFilters((current) => ({ ...current, search }));
          }}
        />
      </Box>

      <ProjectKpiBar
        summary={summary}
        loading={dashboardQuery.isLoading}
        onFilter={handleQuickFilter}
      />

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
        <ProjectFilterSidebar
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
          draft={draftFilters}
          onDraftChange={setDraftFilters}
          onApply={applyFilters}
          onReset={() => setDraftFilters(defaultProjectCommandCenterFilters)}
          onClear={clearFilters}
          customers={customersQuery.data ?? []}
          teams={teamsQuery.data ?? []}
          projectTypes={projectTypesQuery.data ?? []}
          users={usersQuery.data ?? []}
        />

        <Box sx={{ flex: 1, minWidth: 0 }}>
          {dashboardQuery.data ? (
            <>
              <ProjectQuickFilterStrip
                counts={quickCounts}
                activeFilter={appliedFilters.quickFilter}
                onSelect={handleQuickFilter}
              />
              <ProjectCustomerWorkloadStrip
                rows={dashboardQuery.data.customer_workload}
                selectedCustomerId={appliedFilters.customerId}
                onSelect={handleCustomerSelect}
              />
              <ProjectDesignerAvailabilityStrip
                summary={dashboardQuery.data.designer_availability_summary}
                designers={dashboardQuery.data.designer_availability}
                selectedDesignerId={appliedFilters.designerUserId}
                onSelect={handleDesignerSelect}
              />
            </>
          ) : null}

          {tableLoading ? (
            <TableSkeleton rows={10} columns={8} />
          ) : !displayLiveProjects.length && !completedProjects.length ? (
            <EmptyState
              title="No projects found"
              description="Try adjusting your search or filters, or create a new project."
            />
          ) : (
            <>
              {displayLiveProjects.length ? (
                <ProjectListSection
                  title={
                    appliedFilters.showArchived || appliedFilters.quickFilter === 'archived'
                      ? 'Archived Projects'
                      : 'Live Projects'
                  }
                  count={liveCount}
                  projects={displayLiveProjects}
                  customers={customersQuery.data ?? []}
                  users={usersQuery.data ?? []}
                  streams={streamsQuery.data ?? []}
                  teams={teamsQuery.data ?? []}
                  onRowOpen={setSelectedProject}
                  onEdit={setEditProject}
                  onArchive={showArchiveActions ? setArchiveId : undefined}
                />
              ) : null}

              {completedProjects.length &&
              !appliedFilters.showArchived &&
              appliedFilters.quickFilter !== 'archived' ? (
                <ProjectListSection
                  title="Completed Projects"
                  count={completedCount}
                  projects={completedProjects}
                  customers={customersQuery.data ?? []}
                  users={usersQuery.data ?? []}
                  streams={streamsQuery.data ?? []}
                  teams={teamsQuery.data ?? []}
                  defaultExpanded={false}
                  collapsible
                  onRowOpen={setSelectedProject}
                  onEdit={setEditProject}
                />
              ) : null}
            </>
          )}

          {appliedFilters.quickFilter !== 'none' ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              Showing filtered results.
              <Typography
                component="button"
                variant="body2"
                sx={{ ml: 1, border: 0, background: 'none', cursor: 'pointer', color: 'primary.main' }}
                onClick={() => handleQuickFilter('none')}
              >
                Clear quick filter
              </Typography>
            </Alert>
          ) : null}
        </Box>
      </Box>

      <ProjectFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
          void queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.all });
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
          void queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.all });
        }}
      />

      <ProjectRecordDrawer
        project={selectedProject}
        open={Boolean(selectedProject)}
        onClose={() => setSelectedProject(null)}
        onEdit={(project) => {
          setEditProject(project);
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
