import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { navigateWithBack } from '../hooks/useBackNavigation';
import { designTokens } from '../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from '../components/ui/design-system/StickyRecordHeader';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { cloneProject } from '../api/commandCenter';
import { fetchCustomers, fetchStreams, fetchTeams, fetchUsers } from '../api/lookups';
import { dashboardQueryKeys } from '../api/dashboard';
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
import { usePreferences } from '../context/PreferencesContext';
import { useToast } from '../context/ToastContext';
import {
  archiveProject,
  getProjectsPaginated,
  projectQueryKeys,
  restoreProject,
  softDeleteProject,
} from '../services/projectService';
import type { ProjectStage } from '../types';
import { exportToCsv } from '../utils/exportData';
import { filterProjectsForAccessibleTeams, groupProjectsByTeam } from '../utils/projectTeamGroups';
import { getLeaderTeamScopeIds, shouldGroupProjectsByTeamForUser, shouldScopeProjectsByLeaderTeams } from '../utils/projectTeamScope';
import {
  canSelectAllProjectsScope,
  filterProjectsByPortfolioScope,
  groupProjectsByStreamThenTeam,
  normalizeProjectsPortfolioScope,
  type ProjectsPortfolioScope,
} from '../utils/projectStreamScope';
import { canArchiveProject, canCreateProject, canDeleteRecords, canViewArchivedProjects } from '../utils/permissions';
import {
  applyKpiQuickFilter,
  computeProjectPortfolioMetrics,
  countActiveSidebarFilters,
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
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const { preferences, updatePreferences } = usePreferences();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const allowAllScope = canSelectAllProjectsScope(user) || isAdmin;

  const [portfolioScope, setPortfolioScope] = useState<ProjectsPortfolioScope>('my_streams');
  const [streamTab, setStreamTab] = useState<string>('all');
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
  const [gridSessionKey, setGridSessionKey] = useState(0);

  useEffect(() => {
    const saved = normalizeProjectsPortfolioScope(preferences?.projects_portfolio_scope);
    const next =
      saved === 'all' && !allowAllScope ? 'my_streams' : saved;
    setPortfolioScope(next);
  }, [preferences?.projects_portfolio_scope, allowAllScope]);

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
      page: 1,
      page_size: 500,
    }),
    [appliedFilters],
  );

  const projectsQuery = useQuery({
    queryKey: projectQueryKeys.list(listParams),
    queryFn: async () => {
      const page = await getProjectsPaginated(listParams);
      return page.items;
    },
    staleTime: QUERY_STALE_TIMES.projects,
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
  const lookupUsers = usersQuery.data ?? [];

  const filteredProjects = useMemo(
    () => filterProjectsForCommandCenter(projectsQuery.data ?? [], appliedFilters, lookup),
    [appliedFilters, lookup, projectsQuery.data],
  );

  const scopedFilteredProjects = useMemo(
    () =>
      filterProjectsByPortfolioScope(filteredProjects, portfolioScope, user, lookupUsers, {
        isAdmin,
      }),
    [filteredProjects, portfolioScope, user, lookupUsers, isAdmin],
  );

  const liveProjects = useMemo(
    () => sortLiveProjects(scopedFilteredProjects.filter(isLiveProject)),
    [scopedFilteredProjects],
  );

  const completedProjects = useMemo(
    () => sortCompletedProjects(scopedFilteredProjects.filter(isCompletedProject)),
    [scopedFilteredProjects],
  );

  const archivedProjects = useMemo(
    () => scopedFilteredProjects.filter(isArchivedProject),
    [scopedFilteredProjects],
  );

  const displayLiveProjects =
    appliedFilters.showArchived || appliedFilters.quickFilter === 'archived'
      ? archivedProjects
      : liveProjects;

  const leaderTeamIds = getLeaderTeamScopeIds(user);
  const scopeByLeaderTeams = shouldScopeProjectsByLeaderTeams(user?.role_name ?? '', user);

  const teamScopedLiveProjects = useMemo(
    () =>
      filterProjectsForAccessibleTeams(
        displayLiveProjects,
        scopeByLeaderTeams ? leaderTeamIds : undefined,
        isAdmin,
        lookupUsers,
        user?.id,
      ),
    [displayLiveProjects, scopeByLeaderTeams, isAdmin, leaderTeamIds, lookupUsers, user?.id],
  );

  const liveStreamSections = useMemo(
    () =>
      groupProjectsByStreamThenTeam(
        teamScopedLiveProjects,
        streamsQuery.data ?? [],
        teamsQuery.data ?? [],
        lookupUsers,
        {
          leaderTeamIds: scopeByLeaderTeams ? leaderTeamIds : undefined,
          includeEmptyLeaderTeams: scopeByLeaderTeams && portfolioScope === 'my_teams',
        },
      ),
    [
      teamScopedLiveProjects,
      streamsQuery.data,
      teamsQuery.data,
      lookupUsers,
      scopeByLeaderTeams,
      leaderTeamIds,
      portfolioScope,
    ],
  );

  const streamTabOptions = useMemo(() => {
    const options = liveStreamSections
      .filter((section) => section.projectCount > 0)
      .map((section) => ({
        id: section.streamId ?? 'unassigned',
        label: section.streamName,
        count: section.projectCount,
      }));
    return [{ id: 'all', label: 'All streams', count: teamScopedLiveProjects.length }, ...options];
  }, [liveStreamSections, teamScopedLiveProjects.length]);

  useEffect(() => {
    if (streamTab === 'all') return;
    if (!streamTabOptions.some((option) => option.id === streamTab)) {
      setStreamTab('all');
    }
  }, [streamTab, streamTabOptions]);

  const visibleStreamSections = useMemo(() => {
    if (streamTab === 'all') return liveStreamSections.filter((section) => section.projectCount > 0);
    return liveStreamSections.filter(
      (section) => (section.streamId ?? 'unassigned') === streamTab && section.projectCount > 0,
    );
  }, [liveStreamSections, streamTab]);

  const liveProjectTeamGroups = useMemo(
    () =>
      groupProjectsByTeam(teamScopedLiveProjects, teamsQuery.data ?? [], lookupUsers, {
        leaderTeamIds: scopeByLeaderTeams ? leaderTeamIds : undefined,
        includeEmptyLeaderTeams: scopeByLeaderTeams,
      }),
    [teamScopedLiveProjects, teamsQuery.data, lookupUsers, scopeByLeaderTeams, leaderTeamIds],
  );

  const distinctTeamGroupCount = useMemo(
    () => liveProjectTeamGroups.filter((group) => group.projects.length > 0).length,
    [liveProjectTeamGroups],
  );

  const shouldGroupLiveProjectsByTeam = shouldGroupProjectsByTeamForUser(
    user?.role_name ?? '',
    user,
    distinctTeamGroupCount,
  );
  const shouldGroupByStream = visibleStreamSections.length > 1 || streamTab !== 'all';

  const handlePortfolioScopeChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, next: ProjectsPortfolioScope | null) => {
      if (!next) return;
      if (next === 'all' && !allowAllScope) return;
      setPortfolioScope(next);
      setStreamTab('all');
      void updatePreferences({ projects_portfolio_scope: next });
    },
    [allowAllScope, updatePreferences],
  );

  const teamScopedAllProjects = useMemo(
    () =>
      filterProjectsByPortfolioScope(
        filterProjectsForAccessibleTeams(
          projectsQuery.data ?? [],
          scopeByLeaderTeams ? leaderTeamIds : undefined,
          isAdmin,
          lookupUsers,
          user?.id,
        ),
        portfolioScope,
        user,
        lookupUsers,
        { isAdmin },
      ),
    [
      projectsQuery.data,
      scopeByLeaderTeams,
      isAdmin,
      leaderTeamIds,
      lookupUsers,
      user,
      portfolioScope,
    ],
  );

  const portfolioMetrics = useMemo(() => {
    const liveMetrics = computeProjectPortfolioMetrics(teamScopedLiveProjects);
    return {
      ...liveMetrics,
      completedThisMonthCount: computeProjectPortfolioMetrics(teamScopedAllProjects)
        .completedThisMonthCount,
    };
  }, [teamScopedLiveProjects, teamScopedAllProjects]);

  const quickCounts = useMemo(
    () => ({
      inProgress: portfolioMetrics.inProgressCount,
      onHold: portfolioMetrics.onHoldCount,
      overdue: portfolioMetrics.overdueCount,
      dueWeek: portfolioMetrics.dueThisWeekCount,
      notStarted: portfolioMetrics.notStartedCount,
    }),
    [portfolioMetrics],
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
      setAppliedFilters((current) => applyKpiQuickFilter(current, filter));
      setDraftFilters((current) => applyKpiQuickFilter(current, filter));
      setGridSessionKey((key) => key + 1);
      setSearchParams({});
    },
    [setSearchParams],
  );

  const handleExport = useCallback(
    (row: ProjectTableRow) => {
      exportToCsv(
        `project-${row.tool_number}`,
        [
          {
            tool_number: row.tool_number,
            customer_name: row.customer_name,
            part_description: row.part_description,
            designer_name: row.designer_name,
            quoted_hours: row.quoted_hours,
            actual_hours: row.actual_hours,
            execution_status: row.execution_status,
          },
        ],
        [
          { key: 'tool_number', header: 'Tool Number' },
          { key: 'customer_name', header: 'Customer' },
          { key: 'part_description', header: 'Part Description' },
          { key: 'designer_name', header: 'Designer' },
          { key: 'quoted_hours', header: 'Quoted Hours' },
          { key: 'actual_hours', header: 'Actual Hours' },
          { key: 'execution_status', header: 'Status' },
        ],
      );
      showSuccess(`Exported ${row.tool_number}`);
    },
    [showSuccess],
  );

  const showArchiveActions = canArchiveProject(user?.role_name ?? '');
  const showCreateProject = canCreateProject(user?.role_name ?? '');
  const showArchivedLink = user ? canViewArchivedProjects(user) : false;
  const tableLoading = projectsQuery.isPending;

  const subtitle = portfolioMetrics
    ? `${portfolioMetrics.liveCount} active · ${portfolioMetrics.overdueCount} overdue · ${portfolioMetrics.dueThisWeekCount} due this week`
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
            alignItems: 'center',
            gap: 1.5,
            mb: 1,
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.25 }}>
              {shouldGroupLiveProjectsByTeam ? 'Projects' : 'My Projects'}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.15 }}>
              {subtitle}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {showArchivedLink ? (
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => navigateWithBack(navigate, '/projects/archived')}
              >
                Archived
              </ProsohmButton>
            ) : null}
            {showCreateProject ? (
              <ProsohmButton
                buttonVariant="primary"
                startIcon={<AddIcon />}
                onClick={() => setCreateOpen(true)}
              >
                Create Project
              </ProsohmButton>
            ) : null}
          </Box>
        </Box>

        <Box
          sx={{
            position: 'sticky',
            top: APP_TOP_BAR_OFFSET,
            zIndex: 4,
            py: 0.5,
            mb: 0.75,
            bgcolor: designTokens.semantic.background,
          }}
        >
          <FilterToolbar
            dense
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
            <ToggleButtonGroup
              exclusive
              size="small"
              value={portfolioScope}
              onChange={handlePortfolioScopeChange}
              aria-label="Projects portfolio scope"
            >
              <ToggleButton value="my_streams">My streams</ToggleButton>
              <ToggleButton value="my_teams">My teams</ToggleButton>
              {allowAllScope ? <ToggleButton value="all">All</ToggleButton> : null}
            </ToggleButtonGroup>
          </FilterToolbar>

          {streamTabOptions.length > 2 ? (
            <Tabs
              value={streamTab}
              onChange={(_event, value: string) => setStreamTab(value)}
              variant="scrollable"
              scrollButtons="auto"
              sx={{ minHeight: 36, mb: 0.5 }}
            >
              {streamTabOptions.map((option) => (
                <Tab
                  key={option.id}
                  value={option.id}
                  label={`${option.label} (${option.count})`}
                  sx={{ minHeight: 36, py: 0.5, textTransform: 'none' }}
                />
              ))}
            </Tabs>
          ) : null}

          <ProjectKpiBar
            metrics={portfolioMetrics}
            loading={tableLoading}
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
              description="Try adjusting your search, stream scope, or filters, or create a new project."
            />
          ) : (
            <>
              {teamScopedLiveProjects.length ? (
                shouldGroupByStream ? (
                  visibleStreamSections.map((streamSection) => (
                    <Box key={streamSection.streamId ?? 'unassigned'} sx={{ mb: 1.5 }}>
                      <Typography
                        variant="subtitle2"
                        sx={{ fontWeight: 700, mb: 0.75, letterSpacing: '-0.01em' }}
                      >
                        {streamSection.streamName}
                        <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                          {streamSection.projectCount}
                        </Typography>
                      </Typography>
                      {shouldGroupLiveProjectsByTeam
                        ? streamSection.teamGroups.map((group) => (
                            <ProjectListSection
                              key={`${streamSection.streamId ?? 'unassigned'}-${group.teamId ?? 'unassigned'}`}
                              title={group.teamName}
                              count={group.projects.length}
                              projects={group.projects}
                              primary
                              customers={customersQuery.data ?? []}
                              users={usersQuery.data ?? []}
                              streams={streamsQuery.data ?? []}
                              teams={teamsQuery.data ?? []}
                              gridSessionKey={gridSessionKey}
                              onRowOpen={(row) =>
                                navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)
                              }
                              onEdit={setEditProject}
                              onArchive={showArchiveActions ? setArchiveId : undefined}
                              onDuplicate={(projectId) => cloneMutation.mutate(projectId)}
                              onExport={handleExport}
                              onDelete={isAdmin ? setDeleteId : undefined}
                              canDelete={isAdmin}
                            />
                          ))
                        : (
                            <ProjectListSection
                              title={streamSection.streamName}
                              count={streamSection.projectCount}
                              projects={streamSection.teamGroups.flatMap((group) => group.projects)}
                              primary
                              customers={customersQuery.data ?? []}
                              users={usersQuery.data ?? []}
                              streams={streamsQuery.data ?? []}
                              teams={teamsQuery.data ?? []}
                              gridSessionKey={gridSessionKey}
                              onRowOpen={(row) =>
                                navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)
                              }
                              onEdit={setEditProject}
                              onArchive={showArchiveActions ? setArchiveId : undefined}
                              onDuplicate={(projectId) => cloneMutation.mutate(projectId)}
                              onExport={handleExport}
                              onDelete={isAdmin ? setDeleteId : undefined}
                              canDelete={isAdmin}
                            />
                          )}
                    </Box>
                  ))
                ) : shouldGroupLiveProjectsByTeam ? (
                  liveProjectTeamGroups.map((group) => (
                    <ProjectListSection
                      key={group.teamId ?? 'unassigned'}
                      title={group.teamName}
                      count={group.projects.length}
                      projects={group.projects}
                      primary
                      customers={customersQuery.data ?? []}
                      users={usersQuery.data ?? []}
                      streams={streamsQuery.data ?? []}
                      teams={teamsQuery.data ?? []}
                      gridSessionKey={gridSessionKey}
                      onRowOpen={(row) => navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)}
                      onEdit={setEditProject}
                      onArchive={showArchiveActions ? setArchiveId : undefined}
                      onDuplicate={(projectId) => cloneMutation.mutate(projectId)}
                      onExport={handleExport}
                      onDelete={isAdmin ? setDeleteId : undefined}
                      canDelete={isAdmin}
                    />
                  ))
                ) : (
                  <ProjectListSection
                    title={
                      appliedFilters.showArchived || appliedFilters.quickFilter === 'archived'
                        ? 'Archived Projects'
                        : shouldGroupLiveProjectsByTeam
                          ? 'Live Projects'
                          : 'My work'
                    }
                    count={teamScopedLiveProjects.length}
                    projects={teamScopedLiveProjects}
                    primary
                    customers={customersQuery.data ?? []}
                    users={usersQuery.data ?? []}
                    streams={streamsQuery.data ?? []}
                    teams={teamsQuery.data ?? []}
                    gridSessionKey={gridSessionKey}
                    onRowOpen={(row) => navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)}
                    onEdit={setEditProject}
                    onArchive={showArchiveActions ? setArchiveId : undefined}
                    onDuplicate={(projectId) => cloneMutation.mutate(projectId)}
                    onExport={handleExport}
                    onDelete={isAdmin ? setDeleteId : undefined}
                    canDelete={isAdmin}
                  />
                )
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
                  splitActiveHold={false}
                  onRowOpen={(row) => navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)}
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
