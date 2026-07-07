import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Typography,
} from '@mui/material';
import { designTokens } from '../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from '../components/ui/design-system/StickyRecordHeader';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { cloneProject } from '../api/commandCenter';
import { fetchCustomers, fetchStreams, fetchTeams, fetchUsers } from '../api/lookups';
import { dashboardQueryKeys, fetchDashboardSummary } from '../api/dashboard';
import { fetchProjectTypes } from '../api/projectTemplates';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageContainer } from '../components/common/PageContainer';
import { TableSkeleton } from '../components/common/TableSkeleton';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectRecordDrawer } from '../components/projects/ProjectRecordDrawer';
import type { ProjectTableRow } from '../components/projects/ProjectTable';
import { ProjectSearchBar } from '../components/projects/command-center/ProjectSearchBar';
import { ProjectFilterPanel } from '../components/projects/command-center/ProjectFilterPanel';
import { ProjectKpiBar } from '../components/projects/command-center/ProjectKpiBar';
import { ProjectListSection } from '../components/projects/command-center/ProjectListSection';
import { ProjectQuickFilterStrip } from '../components/projects/command-center/ProjectQuickFilterStrip';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { FilterDrawer, FilterToolbar } from '../components/ui/design-system';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  archiveProject,
  getProjects,
  projectQueryKeys,
  restoreProject,
  softDeleteProject,
} from '../services/projectService';
import type { ProjectStage } from '../types';
import { canArchiveProject, canCreateProject, canDeleteRecords } from '../utils/permissions';
import {
  countActiveSidebarFilters,
  countByExecutionStatus,
  countDueThisWeekProjects,
  countNotStartedProjects,
  countOverdueProjects,
  defaultProjectCommandCenterFilters,
  filterProjectsForCommandCenter,
  getProjectActiveFilterChips,
  isArchivedProject,
  isCompletedProject,
  isLiveProject,
  sortCompletedProjects,
  sortLiveProjects,
  type ProjectCommandCenterFilters,
  type ProjectQuickFilter,
} from '../utils/projectCommandCenter';

export function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');

  const [filtersOpen, setFiltersOpen] = useState(false);
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
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);

  useEffect(() => {
    const urlSearch = searchParams.get('search');
    if (urlSearch) {
      setAppliedFilters((current) => ({ ...current, search: urlSearch }));
      setDraftFilters((current) => ({ ...current, search: urlSearch }));
    }
  }, [searchParams]);

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

    const patch = (current: ProjectCommandCenterFilters): ProjectCommandCenterFilters => ({
      ...current,
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
    });

    setDraftFilters(patch);
    setAppliedFilters(patch);
  }, [searchParams]);

  const listParams = useMemo(
    () => ({
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

  const invalidateAll = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
    void queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.all });
  }, [queryClient]);

  const archiveMutation = useMutation({
    mutationFn: archiveProject,
    onSuccess: () => {
      invalidateAll();
      showSuccess('Project archived');
      setArchiveId(null);
      setSelectedProject(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: softDeleteProject,
    onSuccess: () => {
      invalidateAll();
      showSuccess('Project deleted');
      setDeleteId(null);
      setSelectedProject(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const cloneMutation = useMutation({
    mutationFn: cloneProject,
    onSuccess: () => {
      invalidateAll();
      showSuccess('Project duplicated');
    },
    onError: (error: Error) => showError(error.message),
  });

  const restoreMutation = useMutation({
    mutationFn: (projectId: string) => restoreProject(projectId),
    onSuccess: () => {
      invalidateAll();
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

  const filteredProjects = useMemo(
    () => filterProjectsForCommandCenter(projectsQuery.data ?? [], appliedFilters, lookup),
    [appliedFilters, lookup, projectsQuery.data],
  );

  const liveProjects = useMemo(
    () => sortLiveProjects(filteredProjects.filter(isLiveProject)),
    [filteredProjects],
  );

  const completedProjects = useMemo(
    () => sortCompletedProjects(filteredProjects.filter(isCompletedProject)),
    [filteredProjects],
  );

  const archivedProjects = useMemo(
    () => filteredProjects.filter(isArchivedProject),
    [filteredProjects],
  );

  const displayLiveProjects =
    appliedFilters.showArchived || appliedFilters.quickFilter === 'archived'
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
      customerId:
        draftFilters.customerIds.length === 1 ? draftFilters.customerIds[0] : draftFilters.customerId,
    });
    setSearchParams({});
    setFiltersOpen(false);
  }, [draftFilters, setSearchParams]);

  const clearFilters = useCallback(() => {
    setDraftFilters(defaultProjectCommandCenterFilters);
    setAppliedFilters(defaultProjectCommandCenterFilters);
    setSearchParams({});
    setFiltersOpen(false);
  }, [setSearchParams]);

  const resetFilters = useCallback(() => {
    setDraftFilters(defaultProjectCommandCenterFilters);
  }, []);

  const handleQuickFilter = useCallback(
    (filter: ProjectQuickFilter) => {
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
    },
    [setSearchParams],
  );

  const handleExport = useCallback(
    (_row: ProjectTableRow) => {
      showSuccess('Export will be available in a future release.');
    },
    [showSuccess],
  );

  const showArchiveActions = canArchiveProject(user?.role_name ?? '');
  const showCreateProject = canCreateProject(user?.role_name ?? '');
  const tableLoading = projectsQuery.isPending;
  const summary = dashboardQuery.data;

  const subtitle = summary
    ? `${summary.active_projects} active · ${summary.overdue_projects} overdue · ${summary.projects_due_this_week} due this week`
    : 'Operational hub for live engineering projects';

  const activeFilterCount = useMemo(
    () => countActiveSidebarFilters(appliedFilters),
    [appliedFilters],
  );

  const customerNameMap = useMemo(
    () => new Map((customersQuery.data ?? []).map((item) => [item.id, item.name])),
    [customersQuery.data],
  );
  const teamNameMap = useMemo(
    () => new Map((teamsQuery.data ?? []).map((item) => [item.id, item.name])),
    [teamsQuery.data],
  );
  const userNameMap = useMemo(
    () =>
      new Map(
        (usersQuery.data ?? []).map((item) => [
          item.id,
          `${item.first_name} ${item.last_name}`.trim() || item.email,
        ]),
      ),
    [usersQuery.data],
  );

  const projectTypeNameMap = useMemo(
    () => new Map((projectTypesQuery.data ?? []).map((item) => [item.id, item.name])),
    [projectTypesQuery.data],
  );

  const activeFilterChips = useMemo(
    () =>
      getProjectActiveFilterChips(appliedFilters, {
        customerNameMap,
        teamNameMap,
        userNameMap,
        projectTypeNameMap,
      }).map((chip) => ({
        key: chip.key,
        label: chip.label,
        onRemove: () => {
          const next = chip.patch(appliedFilters);
          setAppliedFilters(next);
          setDraftFilters(next);
        },
      })),
    [appliedFilters, customerNameMap, projectTypeNameMap, teamNameMap, userNameMap],
  );

  if (projectsQuery.error) {
    return <ErrorState error={projectsQuery.error} title="Unable to load projects" />;
  }

  return (
    <PageContainer>
      <Box sx={{ minWidth: 0 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 2,
            mb: 2,
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
              Project Command Center
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {subtitle}
            </Typography>
          </Box>
          {showCreateProject ? (
            <ProsohmButton
              buttonVariant="primary"
              startIcon={<AddIcon />}
              onClick={() => setCreateOpen(true)}
              sx={{ flexShrink: 0 }}
            >
              Create Project
            </ProsohmButton>
          ) : null}
        </Box>

        <Box
          sx={{
            position: 'sticky',
            top: APP_TOP_BAR_OFFSET,
            zIndex: 4,
            py: 0.75,
            mb: 1,
            bgcolor: designTokens.semantic.background,
          }}
        >
          <FilterToolbar
            filterButton={{
              activeCount: activeFilterCount,
              onClick: () => setFiltersOpen(true),
            }}
            chips={activeFilterChips}
            onClearAll={clearFilters}
          >
            <Box sx={{ flex: 1, minWidth: 220 }}>
              <ProjectSearchBar
                value={appliedFilters.search}
                onChange={(value) => {
                  setAppliedFilters((current) => ({ ...current, search: value }));
                  setDraftFilters((current) => ({ ...current, search: value }));
                }}
              />
            </Box>
          </FilterToolbar>

          <ProjectKpiBar
            summary={summary}
            loading={dashboardQuery.isLoading}
            activeFilter={appliedFilters.quickFilter}
            onFilter={handleQuickFilter}
          />

          <ProjectQuickFilterStrip
            counts={quickCounts}
            activeFilter={appliedFilters.quickFilter}
            onSelect={handleQuickFilter}
          />
        </Box>

          {tableLoading ? (
            <TableSkeleton rows={8} columns={8} />
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
                  count={displayLiveProjects.length}
                  projects={displayLiveProjects}
                  customers={customersQuery.data ?? []}
                  users={usersQuery.data ?? []}
                  streams={streamsQuery.data ?? []}
                  teams={teamsQuery.data ?? []}
                  onRowOpen={setSelectedProject}
                  onEdit={setEditProject}
                  onArchive={showArchiveActions ? setArchiveId : undefined}
                  onDuplicate={(projectId) => cloneMutation.mutate(projectId)}
                  onExport={handleExport}
                  onDelete={isAdmin ? setDeleteId : undefined}
                  canDelete={isAdmin}
                />
              ) : null}

              {completedProjects.length &&
              !appliedFilters.showArchived &&
              appliedFilters.quickFilter !== 'archived' ? (
                <ProjectListSection
                  title="Completed Projects"
                  count={completedProjects.length}
                  projects={completedProjects}
                  customers={customersQuery.data ?? []}
                  users={usersQuery.data ?? []}
                  streams={streamsQuery.data ?? []}
                  teams={teamsQuery.data ?? []}
                  defaultExpanded={false}
                  collapsible
                  onRowOpen={setSelectedProject}
                  onEdit={setEditProject}
                  onDuplicate={(projectId) => cloneMutation.mutate(projectId)}
                  onExport={handleExport}
                />
              ) : null}
            </>
          )}
      </Box>

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Project filters"
        subtitle="Refine the project list"
        onApply={applyFilters}
        onReset={resetFilters}
      >
        <ProjectFilterPanel
          draft={draftFilters}
          onDraftChange={setDraftFilters}
          customers={customersQuery.data ?? []}
          teams={teamsQuery.data ?? []}
          projectTypes={projectTypesQuery.data ?? []}
          users={usersQuery.data ?? []}
        />
      </FilterDrawer>

      <ProjectFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          invalidateAll();
        }}
      />

      <ProjectFormDialog
        open={Boolean(editProject)}
        onClose={() => setEditProject(null)}
        project={editProject ?? undefined}
        onUpdated={() => {
          setEditProject(null);
          setSelectedProject(null);
          invalidateAll();
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
        danger
        loading={archiveMutation.isPending}
        onClose={() => setArchiveId(null)}
        onConfirm={() => archiveId && archiveMutation.mutate(archiveId)}
      />

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete project?"
        message="This project will be soft-deleted and removed from active lists."
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
      />
    </PageContainer>
  );
}
