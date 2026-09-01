import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { navigateWithBack } from '../hooks/useBackNavigation';
import { useOpenCreateFromQuery } from '../hooks/useOpenCreateFromQuery';
import { designTokens } from '../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from '../components/ui/design-system/StickyRecordHeader';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { cloneProject } from '../api/commandCenter';
import { fetchCustomers, fetchProjectSmallTaskTypes, fetchStreams, fetchTeams, fetchUsers } from '../api/lookups';
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
import { ProjectTeamCommandCenter } from '../components/projects/command-center/ProjectTeamCommandCenter';
import { groupProjectsByTeamThenStream } from '../utils/projectTeamStreamHierarchy';
import { ProjectClassificationFilterStrip } from '../components/projects/command-center/ProjectClassificationFilterStrip';
import { ProjectQuickFilterStrip } from '../components/projects/command-center/ProjectQuickFilterStrip';
import { ProjectStreamCards } from '../components/projects/command-center/ProjectStreamCards';
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
import {
  filterProjectsForAccessibleTeams,
  resolveEffectiveProjectTeamId,
} from '../utils/projectTeamGroups';
import { getLeaderTeamScopeIds, shouldScopeProjectsByLeaderTeams } from '../utils/projectTeamScope';
import {
  canSelectAllProjectsScope,
  filterProjectsByPortfolioScope,
  shouldShowProjectStreamFilters,
  getUserRelevantStreamIds,
  type ProjectsPortfolioScope,
} from '../utils/projectStreamScope';
import {
  clearProjectsPageSession,
  loadProjectsPageSession,
  saveProjectsPageSession,
} from '../utils/projectsPageSession';
import { canArchiveProject, canCreateProject, canDeleteProject, canEditProject, canViewArchivedProjects, accessContextFromUser, isAdminRole } from '../utils/permissions';
import {
  applyClassificationFilter,
  applyKpiQuickFilter,
  computeProjectPortfolioMetrics,
  countActiveSidebarFilters,
  defaultProjectCommandCenterFilters,
  filterProjectsForCommandCenter,
  getProjectActiveFilterChips,
  isArchivedProject,
  isCompletedProject,
  isLiveProject,
  sortLiveProjects,
  type ProjectCommandCenterFilters,
  type ProjectClassificationFilter,
  type ProjectQuickFilter,
} from '../utils/projectCommandCenter';

function initialFiltersFromSession(): ProjectCommandCenterFilters {
  return loadProjectsPageSession()?.filters ?? defaultProjectCommandCenterFilters;
}

function initialSelectedStreamIdsFromSession(): string[] {
  return loadProjectsPageSession()?.selectedStreamIds ?? [];
}

function initialSelectedTeamIdsFromSession(): string[] {
  return loadProjectsPageSession()?.selectedTeamIds ?? [];
}

function searchParamsHaveDeepLinks(params: URLSearchParams): boolean {
  return Boolean(
    params.get('execution_status') ||
      params.get('project_stage') ||
      params.get('team_id') ||
      params.get('customer_id') ||
      params.get('due') ||
      params.get('completed') ||
      params.get('lifecycle') ||
      params.get('search'),
  );
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const { preferences, updatePreferences } = usePreferences();
  const canDelete = canDeleteProject(access);
  const isAdmin = isAdminRole(user?.role_name ?? '');
  const allowAllScope = canSelectAllProjectsScope(user) || isAdmin;
  const showStreamFilters = shouldShowProjectStreamFilters(user);
  const userStreamIds = useMemo(() => new Set(getUserRelevantStreamIds(user)), [user]);

  // Simplified portfolio: team-scoped for everyone who has teams; All only for unrestricted.
  const [portfolioScope, setPortfolioScope] = useState<ProjectsPortfolioScope>(
    allowAllScope ? 'all' : 'my_teams',
  );
  const [selectedStreamIds, setSelectedStreamIds] = useState<string[]>(
    initialSelectedStreamIdsFromSession,
  );
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[]>(
    initialSelectedTeamIdsFromSession,
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [draftFilters, setDraftFilters] = useState<ProjectCommandCenterFilters>(
    initialFiltersFromSession,
  );
  const [appliedFilters, setAppliedFilters] = useState<ProjectCommandCenterFilters>(
    initialFiltersFromSession,
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [editProject, setEditProject] = useState<ProjectTableRow | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectTableRow | null>(null);
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [restoreId, setRestoreId] = useState<string | null>(null);
  const [gridSessionKey, setGridSessionKey] = useState(0);
  const deepLinkAppliedRef = useRef(false);

  useEffect(() => {
    // Prefer team scope; only restore "all" for unrestricted users.
    if (allowAllScope) {
      const saved = preferences?.projects_portfolio_scope;
      if (saved === 'all' || saved === 'my_teams' || saved === 'my_streams') {
        setPortfolioScope(saved);
      }
    } else {
      setPortfolioScope('my_teams');
    }
    if (preferences?.projects_cc_layout) {
      setAppliedFilters((current) => ({
        ...current,
        layout: preferences.projects_cc_layout ?? current.layout,
      }));
    }
  }, [preferences?.projects_portfolio_scope, preferences?.projects_cc_layout, allowAllScope]);

  // Persist filters + stream/team selection so navigating away and back restores them.
  useEffect(() => {
    saveProjectsPageSession({
      filters: appliedFilters,
      selectedStreamIds,
      selectedTeamIds,
    });
  }, [appliedFilters, selectedStreamIds, selectedTeamIds]);

  // Shareable URL state (non-sensitive filters only).
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    const setOrDelete = (key: string, value: string | undefined) => {
      if (value) next.set(key, value);
      else next.delete(key);
    };
    setOrDelete('search', appliedFilters.search.trim() || undefined);
    setOrDelete(
      'execution_status',
      appliedFilters.executionStatus === 'all' ? undefined : appliedFilters.executionStatus,
    );
    setOrDelete('health', appliedFilters.health === 'all' ? undefined : appliedFilters.health);
    setOrDelete('due', appliedFilters.dueDate === 'all' ? undefined : appliedFilters.dueDate);
    setOrDelete('layout', appliedFilters.layout === 'list' ? undefined : appliedFilters.layout);
    setOrDelete('group_by', appliedFilters.groupBy === 'none' ? undefined : appliedFilters.groupBy);
    if (selectedStreamIds.length === 1) next.set('stream_id', selectedStreamIds[0]);
    else next.delete('stream_id');
    if (selectedTeamIds.length === 1) next.set('team_id', selectedTeamIds[0]);
    else next.delete('team_id');
    if (appliedFilters.workstreamIds.length === 1) {
      next.set('workstream_id', appliedFilters.workstreamIds[0]);
    } else {
      next.delete('workstream_id');
    }
    const current = searchParams.toString();
    const upcoming = next.toString();
    if (current !== upcoming) {
      setSearchParams(next, { replace: true });
    }
  }, [appliedFilters, selectedStreamIds, selectedTeamIds, searchParams, setSearchParams]);

  useEffect(() => {
    if (deepLinkAppliedRef.current) return;
    if (!searchParamsHaveDeepLinks(searchParams)) return;
    deepLinkAppliedRef.current = true;

    const urlSearch = searchParams.get('search');
    const executionStatus = searchParams.get('execution_status');
    const projectStage = searchParams.get('project_stage');
    const teamId = searchParams.get('team_id');
    const customerId = searchParams.get('customer_id');
    const due = searchParams.get('due');
    const completed = searchParams.get('completed');
    const lifecycle = searchParams.get('lifecycle');

    const patch = (current: ProjectCommandCenterFilters): ProjectCommandCenterFilters => ({
      ...current,
      search: urlSearch ?? current.search,
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
      execution_status:
        appliedFilters.executionStatus === 'all' ? undefined : appliedFilters.executionStatus,
      customer_ids:
        appliedFilters.customerIds.length > 0 ? appliedFilters.customerIds : undefined,
      team_ids:
        selectedTeamIds.length > 0
          ? selectedTeamIds
          : appliedFilters.teamIds.length > 0
            ? appliedFilters.teamIds
            : undefined,
      stream_ids:
        selectedStreamIds.length > 0
          ? selectedStreamIds
          : appliedFilters.streamIds.length > 0
            ? appliedFilters.streamIds
            : undefined,
      project_classification:
        appliedFilters.projectClassification === 'all'
          ? undefined
          : appliedFilters.projectClassification,
      small_task_type_id:
        appliedFilters.smallTaskTypeId === 'all' ? undefined : appliedFilters.smallTaskTypeId,
      workstream_ids:
        appliedFilters.workstreamIds.length > 0 ? appliedFilters.workstreamIds : undefined,
      project_type_id:
        appliedFilters.projectTypeId === 'all' ? undefined : appliedFilters.projectTypeId,
      design_leader_id:
        appliedFilters.designLeaderId === 'all' ? undefined : appliedFilters.designLeaderId,
      designer_id:
        appliedFilters.designerId === 'all' ? undefined : appliedFilters.designerId,
      surfacer_id:
        appliedFilters.surfacerId === 'all' ? undefined : appliedFilters.surfacerId,
      health: appliedFilters.health === 'all' ? undefined : appliedFilters.health,
      priority: appliedFilters.priority === 'all' ? undefined : appliedFilters.priority,
      q: appliedFilters.search.trim() || undefined,
      due: appliedFilters.dueDate === 'all' ? undefined : appliedFilters.dueDate,
      page: 1,
      page_size: 100,
    }),
    [appliedFilters, selectedStreamIds, selectedTeamIds],
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

  const smallTaskTypesQuery = useQuery({
    queryKey: ['lookups', 'project-small-task-types'],
    queryFn: fetchProjectSmallTaskTypes,
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

  const deleteTarget = useMemo(
    () => (projectsQuery.data ?? []).find((row) => row.id === deleteId) ?? null,
    [deleteId, projectsQuery.data],
  );

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
      streams: (streamsQuery.data ?? []).map((stream) => ({
        id: stream.id,
        name: stream.name,
      })),
      smallTaskTypes: (smallTaskTypesQuery.data ?? []).map((taskType) => ({
        id: taskType.id,
        name: taskType.name,
      })),
    }),
    [customersQuery.data, teamsQuery.data, usersQuery.data, streamsQuery.data, smallTaskTypesQuery.data],
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

  const streamFilteredProjects = useMemo(() => {
    const streamIds =
      selectedStreamIds.length > 0 ? selectedStreamIds : appliedFilters.streamIds;
    if (!streamIds.length) return scopedFilteredProjects;
    const allowed = new Set(streamIds);
    return scopedFilteredProjects.filter(
      (project) => project.stream_id != null && allowed.has(project.stream_id),
    );
  }, [scopedFilteredProjects, selectedStreamIds, appliedFilters.streamIds]);

  const teamFilteredProjects = useMemo(() => {
    if (!selectedTeamIds.length) return streamFilteredProjects;
    const allowed = new Set(selectedTeamIds);
    const usersById = new Map(lookupUsers.map((item) => [item.id, item]));
    return streamFilteredProjects.filter((project) => {
      const teamId = resolveEffectiveProjectTeamId(project, usersById);
      return teamId != null && allowed.has(teamId);
    });
  }, [streamFilteredProjects, selectedTeamIds, lookupUsers]);

  const liveProjects = useMemo(
    () => sortLiveProjects(teamFilteredProjects.filter(isLiveProject)),
    [teamFilteredProjects],
  );

  const archivedProjects = useMemo(
    () => teamFilteredProjects.filter(isArchivedProject),
    [teamFilteredProjects],
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

  /** Streams with projects — limited to streams this user handles unless unrestricted. */
  const streamFilterOptions = useMemo(() => {
    const activeStreams = (streamsQuery.data ?? []).filter(
      (stream) => stream.is_active !== false,
    );
    const activeCounts = new Map<string, number>();
    const pastCounts = new Map<string, number>();
    for (const project of scopedFilteredProjects) {
      if (!project.stream_id) continue;
      if (isArchivedProject(project)) {
        pastCounts.set(project.stream_id, (pastCounts.get(project.stream_id) ?? 0) + 1);
        continue;
      }
      if (isCompletedProject(project)) {
        pastCounts.set(project.stream_id, (pastCounts.get(project.stream_id) ?? 0) + 1);
        continue;
      }
      if (isLiveProject(project)) {
        activeCounts.set(project.stream_id, (activeCounts.get(project.stream_id) ?? 0) + 1);
      }
    }
    return activeStreams
      .map((stream) => ({
        id: stream.id,
        label: stream.name,
        activeCount: activeCounts.get(stream.id) ?? 0,
        pastCount: pastCounts.get(stream.id) ?? 0,
      }))
      .filter((option) => option.activeCount > 0 || option.pastCount > 0)
      .filter((option) => allowAllScope || userStreamIds.size === 0 || userStreamIds.has(option.id))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [streamsQuery.data, scopedFilteredProjects, allowAllScope, userStreamIds]);

  useEffect(() => {
    if (!selectedStreamIds.length) return;
    const valid = new Set(streamFilterOptions.map((option) => option.id));
    const next = selectedStreamIds.filter((id) => valid.has(id));
    if (next.length !== selectedStreamIds.length) {
      setSelectedStreamIds(next);
    }
  }, [selectedStreamIds, streamFilterOptions]);

  /** Teams with projects in the current stream-scoped portfolio (before team card filter). */
  const teamFilterOptions = useMemo(() => {
    const usersById = new Map(lookupUsers.map((item) => [item.id, item]));
    const teamNameById = new Map((teamsQuery.data ?? []).map((team) => [team.id, team.name]));
    const counts = new Map<string, number>();
    for (const project of streamFilteredProjects) {
      if (isArchivedProject(project) || isCompletedProject(project)) continue;
      if (!isLiveProject(project)) continue;
      const teamId = resolveEffectiveProjectTeamId(project, usersById);
      if (!teamId) continue;
      counts.set(teamId, (counts.get(teamId) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([id, count]) => ({
        id,
        label: teamNameById.get(id) ?? 'Unknown team',
        count,
      }))
      .filter((option) => option.count > 0)
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [streamFilteredProjects, lookupUsers, teamsQuery.data]);

  useEffect(() => {
    if (!selectedTeamIds.length) return;
    const valid = new Set(teamFilterOptions.map((option) => option.id));
    const next = selectedTeamIds.filter((id) => valid.has(id));
    if (next.length !== selectedTeamIds.length) {
      setSelectedTeamIds(next);
    }
  }, [selectedTeamIds, teamFilterOptions]);

  const commandCenterProjects = useMemo(
    () =>
      filterProjectsForAccessibleTeams(
        teamFilteredProjects,
        scopeByLeaderTeams ? leaderTeamIds : undefined,
        isAdmin,
        lookupUsers,
        user?.id,
      ),
    [
      teamFilteredProjects,
      scopeByLeaderTeams,
      leaderTeamIds,
      isAdmin,
      lookupUsers,
      user?.id,
    ],
  );

  const teamStreamSections = useMemo(
    () =>
      groupProjectsByTeamThenStream(
        commandCenterProjects,
        teamsQuery.data ?? [],
        streamsQuery.data ?? [],
        lookupUsers,
        {
          leaderTeamIds: scopeByLeaderTeams ? leaderTeamIds : undefined,
          includeEmptyLeaderTeams: false,
          preferredStreamOrder:
            selectedStreamIds.length > 0
              ? selectedStreamIds
              : streamFilterOptions.map((option) => option.id),
        },
      ),
    [
      commandCenterProjects,
      teamsQuery.data,
      streamsQuery.data,
      lookupUsers,
      scopeByLeaderTeams,
      leaderTeamIds,
      selectedStreamIds,
      streamFilterOptions,
    ],
  );

  const handlePortfolioScopeChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, next: ProjectsPortfolioScope | null) => {
      if (!next) return;
      if (next === 'all' && !allowAllScope) return;
      setPortfolioScope(next);
      setSelectedStreamIds([]);
      setSelectedTeamIds([]);
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
    setSelectedStreamIds([]);
    setSelectedTeamIds([]);
    clearProjectsPageSession();
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

  const showArchiveActions = canArchiveProject(access);
  const showCreateProject = canCreateProject(access);
  const showEditProject = canEditProject(access);
  useOpenCreateFromQuery(() => {
    if (showCreateProject) setCreateOpen(true);
  });
  const handleEdit = showEditProject ? setEditProject : undefined;
  const handleDuplicate = showCreateProject
    ? (projectId: string) => cloneMutation.mutate(projectId)
    : undefined;
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
  const streamNameMap = useMemo(
    () => new Map((streamsQuery.data ?? []).map((item) => [item.id, item.name])),
    [streamsQuery.data],
  );
  const smallTaskTypeNameMap = useMemo(
    () => new Map((smallTaskTypesQuery.data ?? []).map((item) => [item.id, item.name])),
    [smallTaskTypesQuery.data],
  );

  const classificationCounts = useMemo(
    () => ({
      fullDesign: portfolioMetrics?.fullDesignCount ?? 0,
      smallTask: portfolioMetrics?.smallTaskCount ?? 0,
      unclassified: portfolioMetrics?.unclassifiedCount ?? 0,
    }),
    [portfolioMetrics],
  );

  const handleClassificationFilter = useCallback(
    (classification: ProjectClassificationFilter) => {
      const next = applyClassificationFilter(appliedFilters, classification);
      setAppliedFilters(next);
      setDraftFilters(next);
    },
    [appliedFilters],
  );

  const activeFilterChips = useMemo(
    () =>
      getProjectActiveFilterChips(appliedFilters, {
        customerNameMap,
        teamNameMap,
        streamNameMap,
        userNameMap,
        projectTypeNameMap,
        smallTaskTypeNameMap,
      }).map((chip) => ({
        key: chip.key,
        label: chip.label,
        onRemove: () => {
          const next = chip.patch(appliedFilters);
          setAppliedFilters(next);
          setDraftFilters(next);
        },
      })),
    [appliedFilters, customerNameMap, projectTypeNameMap, streamNameMap, smallTaskTypeNameMap, teamNameMap, userNameMap],
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
              Project Command Center
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

        {showStreamFilters && streamFilterOptions.length > 1 ? (
          <ProjectStreamCards
            options={streamFilterOptions}
            selectedIds={selectedStreamIds}
            onChange={(next) => {
              setSelectedStreamIds(next);
              setSelectedTeamIds([]);
            }}
          />
        ) : null}

        <Box
          sx={{
            position: 'sticky',
            top: APP_TOP_BAR_OFFSET,
            zIndex: 3,
            bgcolor: 'background.default',
            pt: 0.5,
            pb: 0.75,
            mb: 0.5,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <FilterToolbar
            filterButton={{
              activeCount: activeFilterCount,
              onClick: () => {
                setDraftFilters(appliedFilters);
                setFiltersOpen(true);
              },
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
            {allowAllScope ? (
              <ToggleButtonGroup
                exclusive
                size="small"
                value={portfolioScope === 'all' ? 'all' : 'my_teams'}
                onChange={handlePortfolioScopeChange}
                aria-label="Projects portfolio scope"
                sx={{
                  bgcolor: designTokens.semantic.card,
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: `${designTokens.radius.sm}px`,
                  '& .MuiToggleButton-root': {
                    px: 1.1,
                    py: 0.4,
                    textTransform: 'none',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    border: 0,
                    '&.Mui-selected': {
                      bgcolor: designTokens.semantic.primarySoft,
                      color: designTokens.semantic.primary,
                    },
                  },
                }}
              >
                <ToggleButton value="my_teams">My teams</ToggleButton>
                <ToggleButton value="all">All</ToggleButton>
              </ToggleButtonGroup>
            ) : null}
          </FilterToolbar>

          <ProjectKpiBar
            metrics={portfolioMetrics}
            loading={tableLoading}
            activeFilter={appliedFilters.quickFilter}
            onFilter={handleQuickFilter}
          />

          <ProjectClassificationFilterStrip
            counts={classificationCounts}
            activeClassification={appliedFilters.projectClassification}
            onSelect={handleClassificationFilter}
            showUnclassifiedReview={isAdmin}
          />

          <ProjectQuickFilterStrip
            counts={quickCounts}
            activeFilter={appliedFilters.quickFilter}
            onSelect={handleQuickFilter}
          />
        </Box>

        <Box sx={{ width: '100%' }}>
          {tableLoading ? (
            <TableSkeleton rows={8} columns={8} />
          ) : !commandCenterProjects.length ? (
            <EmptyState
              title="No projects found"
              description={
                showCreateProject
                  ? 'Try adjusting your search or filters, or create a new project.'
                  : 'Try adjusting your search or filters.'
              }
            />
          ) : (
            <ProjectTeamCommandCenter
              sections={teamStreamSections}
              customers={customersQuery.data ?? []}
              users={usersQuery.data ?? []}
              streams={streamsQuery.data ?? []}
              teams={teamsQuery.data ?? []}
              gridSessionKey={gridSessionKey}
              onRowOpen={(row) => navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)}
              onEdit={handleEdit}
              onArchive={showArchiveActions ? setArchiveId : undefined}
              onDuplicate={handleDuplicate}
              onExport={handleExport}
              onDelete={canDelete ? setDeleteId : undefined}
              canDelete={canDelete}
            />
          )}
        </Box>
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
          streams={streamsQuery.data ?? []}
          projectTypes={projectTypesQuery.data ?? []}
          smallTaskTypes={smallTaskTypesQuery.data ?? []}
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
        onEdit={
          showEditProject
            ? (project) => {
                setEditProject(project);
              }
            : undefined
        }
        onArchive={(projectId) => setArchiveId(projectId)}
        canArchive={showArchiveActions}
        canDuplicate={showCreateProject}
        canDelete={canDelete}
        onDelete={(projectId) => setDeleteId(projectId)}
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
        message={
          deleteTarget && Number(deleteTarget.actual_hours) > 0
            ? `This removes ${deleteTarget.tool_number} from active project management. Timesheets, milestones, and post-completion hours are kept for history. Completed projects stay recoverable from Deleted Projects. This does not permanently destroy records.`
            : 'This removes the project from active project management. Related timesheets, milestones, and history are kept. The project can be restored from Deleted Projects. This is not a permanent erase.'
        }
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
      />
    </PageContainer>
  );
}
