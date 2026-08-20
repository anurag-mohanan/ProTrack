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
import { ProjectStreamCards } from '../components/projects/command-center/ProjectStreamCards';
import { ProjectStreamPanel } from '../components/projects/command-center/ProjectStreamPanel';
import { ProjectTeamFilterRail } from '../components/projects/command-center/ProjectTeamFilterRail';
import { ProjectViewControlCards } from '../components/projects/command-center/ProjectViewControlCards';
import { ProjectWorkstreamSection } from '../components/projects/command-center/ProjectWorkstreamSection';
import { WorkstreamSectionsManager } from '../components/projects/command-center/WorkstreamSectionsManager';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { FilterDrawer, FilterToolbar } from '../components/ui/design-system';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { usePreferences } from '../context/PreferencesContext';
import { useToast } from '../context/ToastContext';
import {
  archiveProject,
  createProjectView,
  getProjectViews,
  getProjectsPaginated,
  getProjectsSummary,
  projectQueryKeys,
  restoreProject,
  softDeleteProject,
} from '../services/projectService';
import type { ProjectSavedView, ProjectStage, Workstream } from '../types';
import { workstreamsApi } from '../api/resources';
import { exportToCsv } from '../utils/exportData';
import { filterProjectsForAccessibleTeams, groupProjectsByTeam, resolveEffectiveProjectTeamId } from '../utils/projectTeamGroups';
import {
  groupProjectsByWorkstream,
  loadWorkstreamSectionPrefs,
  persistWorkstreamSectionPrefs,
  type WorkstreamSectionPrefs,
} from '../utils/projectWorkstreamGroups';
import { getLeaderTeamScopeIds, shouldGroupProjectsByTeamForUser, shouldScopeProjectsByLeaderTeams } from '../utils/projectTeamScope';
import {
  canSelectAllProjectsScope,
  filterProjectsByPortfolioScope,
  groupProjectsByStreamThenTeam,
  normalizeProjectsPortfolioScope,
  type ProjectsPortfolioScope,
} from '../utils/projectStreamScope';
import {
  clearProjectsPageSession,
  loadProjectsPageSession,
  saveProjectsPageSession,
} from '../utils/projectsPageSession';
import { canArchiveProject, canCreateProject, canDeleteProject, canEditProject, canViewArchivedProjects, accessContextFromUser, isAdminRole } from '../utils/permissions';
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

  const [portfolioScope, setPortfolioScope] = useState<ProjectsPortfolioScope>('my_streams');
  const [selectedStreamIds, setSelectedStreamIds] = useState<string[]>(
    initialSelectedStreamIdsFromSession,
  );
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[]>(
    initialSelectedTeamIdsFromSession,
  );
  const [, setSelectedStatusIds] = useState<string[]>([]);
  const [showWorkstreamCards, setShowWorkstreamCards] = useState(true);
  const [showTeamCards, setShowTeamCards] = useState(true);
  const [showStatusCards, setShowStatusCards] = useState(true);
  const [savedViews, setSavedViews] = useState<ProjectSavedView[]>([]);
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
  const [workstreamPrefs, setWorkstreamPrefs] = useState<WorkstreamSectionPrefs>(() =>
    loadWorkstreamSectionPrefs(),
  );
  const [workstreamManagerOpen, setWorkstreamManagerOpen] = useState(false);
  const deepLinkAppliedRef = useRef(false);

  const updateWorkstreamPrefs = useCallback((next: WorkstreamSectionPrefs) => {
    setWorkstreamPrefs(next);
    persistWorkstreamSectionPrefs(next);
  }, []);

  useEffect(() => {
    const saved = normalizeProjectsPortfolioScope(preferences?.projects_portfolio_scope);
    const next =
      saved === 'all' && !allowAllScope ? 'my_streams' : saved;
    setPortfolioScope(next);
    if (typeof preferences?.projects_cc_show_workstreams === 'boolean') {
      setShowWorkstreamCards(preferences.projects_cc_show_workstreams);
    }
    if (typeof preferences?.projects_cc_show_teams === 'boolean') {
      setShowTeamCards(preferences.projects_cc_show_teams);
    }
    if (typeof preferences?.projects_cc_show_status === 'boolean') {
      setShowStatusCards(preferences.projects_cc_show_status);
    }
    if (preferences?.projects_cc_layout) {
      setAppliedFilters((current) => ({
        ...current,
        layout: preferences.projects_cc_layout ?? current.layout,
      }));
    }
  }, [preferences?.projects_portfolio_scope, preferences?.projects_cc_show_workstreams, preferences?.projects_cc_show_teams, preferences?.projects_cc_show_status, preferences?.projects_cc_layout, allowAllScope]);

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
      stream_ids: selectedStreamIds.length > 0 ? selectedStreamIds : undefined,
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

  const workstreamsQuery = useQuery({
    queryKey: ['lookups', 'workstreams'],
    queryFn: () => workstreamsApi.list({ limit: 500, is_active: true }),
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const summaryQuery = useQuery({
    queryKey: ['projects', 'summary', listParams],
    queryFn: () => getProjectsSummary(listParams),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  useEffect(() => {
    void getProjectViews()
      .then(setSavedViews)
      .catch(() => setSavedViews([]));
  }, []);

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

  const streamFilteredProjects = useMemo(() => {
    if (!selectedStreamIds.length) return scopedFilteredProjects;
    const allowed = new Set(selectedStreamIds);
    return scopedFilteredProjects.filter(
      (project) => project.stream_id != null && allowed.has(project.stream_id),
    );
  }, [scopedFilteredProjects, selectedStreamIds]);

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

  const completedProjects = useMemo(
    () => sortCompletedProjects(teamFilteredProjects.filter(isCompletedProject)),
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
  // Always hide empty team shells — card filters + list filters make zero-count sections noise.
  const includeEmptyLeaderTeams = false;

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

  /** Streams with active and/or past projects only (never empty streams). */
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
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [streamsQuery.data, scopedFilteredProjects]);

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

  const liveStreamSections = useMemo(
    () =>
      groupProjectsByStreamThenTeam(
        teamScopedLiveProjects,
        streamsQuery.data ?? [],
        teamsQuery.data ?? [],
        lookupUsers,
        {
          leaderTeamIds: scopeByLeaderTeams ? leaderTeamIds : undefined,
          includeEmptyLeaderTeams,
          preferredStreamOrder:
            selectedStreamIds.length > 0
              ? selectedStreamIds
              : streamFilterOptions.map((option) => option.id),
        },
      ).filter((section) => section.projectCount > 0),
    [
      teamScopedLiveProjects,
      streamsQuery.data,
      teamsQuery.data,
      lookupUsers,
      scopeByLeaderTeams,
      leaderTeamIds,
      includeEmptyLeaderTeams,
      selectedStreamIds,
      streamFilterOptions,
    ],
  );

  const visibleStreamSections = liveStreamSections;
  const multiStreamView = streamFilterOptions.length >= 1;
  const showStreamChrome =
    streamFilterOptions.length > 1 &&
    (selectedStreamIds.length === 0 || selectedStreamIds.length > 1);
  const shouldGroupByStream = multiStreamView;

  const liveProjectTeamGroups = useMemo(
    () =>
      groupProjectsByTeam(teamScopedLiveProjects, teamsQuery.data ?? [], lookupUsers, {
        leaderTeamIds: scopeByLeaderTeams ? leaderTeamIds : undefined,
        includeEmptyLeaderTeams: false,
      }).filter((group) => group.projects.length > 0),
    [teamScopedLiveProjects, teamsQuery.data, lookupUsers, scopeByLeaderTeams, leaderTeamIds],
  );

  const liveWorkstreamGroups = useMemo(
    () =>
      groupProjectsByWorkstream(teamScopedLiveProjects, workstreamsQuery.data ?? [], {
        includeEmpty: false,
        projectTypes: projectTypesQuery.data ?? [],
        prefs: workstreamPrefs,
      }),
    [teamScopedLiveProjects, workstreamsQuery.data, projectTypesQuery.data, workstreamPrefs],
  );

  /** Workstream sections are the default Command Center layout when catalog exists. */
  const useWorkstreamSections =
    appliedFilters.groupBy === 'workstream' ||
    (appliedFilters.groupBy === 'none' && (workstreamsQuery.data?.length ?? 0) > 0);

  const liveCustomerGroups = useMemo(() => {
    const map = new Map<string, { id: string; label: string; projects: typeof teamScopedLiveProjects }>();
    for (const project of teamScopedLiveProjects) {
      const id = project.customer_id;
      const label = project.customer_name ?? 'Customer';
      const existing = map.get(id);
      if (existing) existing.projects.push(project);
      else map.set(id, { id, label, projects: [project] });
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [teamScopedLiveProjects]);

  const liveHealthGroups = useMemo(() => {
    const order = ['red', 'yellow', 'green'] as const;
    return order
      .map((health) => ({
        id: health,
        label: health === 'red' ? 'At risk' : health === 'yellow' ? 'Watch' : 'On track',
        projects: teamScopedLiveProjects.filter((p) => p.health === health),
      }))
      .filter((g) => g.projects.length > 0);
  }, [teamScopedLiveProjects]);

  const distinctTeamGroupCount = useMemo(
    () => liveProjectTeamGroups.length,
    [liveProjectTeamGroups],
  );

  const shouldGroupLiveProjectsByTeam =
    appliedFilters.groupBy === 'team' ||
    (appliedFilters.groupBy === 'none' &&
      shouldGroupProjectsByTeamForUser(user?.role_name ?? '', user, distinctTeamGroupCount));

  const shouldGroupByWorkstream = useWorkstreamSections;
  const shouldGroupByCustomer = appliedFilters.groupBy === 'customer';
  const shouldGroupByHealth = appliedFilters.groupBy === 'health';

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

        <ProjectStreamCards
          options={streamFilterOptions}
          selectedIds={selectedStreamIds}
          onChange={(next) => {
            setSelectedStreamIds(next);
            setSelectedTeamIds([]);
          }}
        />

        <ProjectViewControlCards
          workstreams={(workstreamsQuery.data ?? []).map((ws: Workstream) => ({
            id: ws.id,
            label: ws.name,
            count: (projectsQuery.data ?? []).filter((project) =>
              (project.workstreams ?? []).some((link) => link.workstream_id === ws.id),
            ).length,
          }))}
          teams={teamFilterOptions}
          statusBuckets={[
            { id: 'currently_being_worked_on', label: 'In Progress' },
            { id: 'planning', label: 'Planning' },
            { id: 'on_hold', label: 'On Hold' },
            { id: 'due_week', label: 'Due Soon' },
            { id: 'overdue', label: 'Overdue' },
            { id: 'at_risk', label: 'At Risk' },
          ]}
          selectedWorkstreamIds={appliedFilters.workstreamIds}
          selectedTeamIds={selectedTeamIds}
          selectedStatusIds={appliedFilters.statusBucketIds}
          onWorkstreamsChange={(ids) => {
            setAppliedFilters((current) => ({ ...current, workstreamIds: ids }));
            setDraftFilters((current) => ({ ...current, workstreamIds: ids }));
          }}
          onTeamsChange={setSelectedTeamIds}
          onStatusChange={(ids) => {
            setSelectedStatusIds(ids);
            setAppliedFilters((current) => ({ ...current, statusBucketIds: ids }));
            setDraftFilters((current) => ({ ...current, statusBucketIds: ids }));
          }}
          showWorkstreams={showWorkstreamCards}
          showTeams={showTeamCards}
          showStatus={showStatusCards}
          onShowWorkstreamsChange={(value) => {
            setShowWorkstreamCards(value);
            void updatePreferences({ projects_cc_show_workstreams: value });
          }}
          onShowTeamsChange={(value) => {
            setShowTeamCards(value);
            void updatePreferences({ projects_cc_show_teams: value });
          }}
          onShowStatusChange={(value) => {
            setShowStatusCards(value);
            void updatePreferences({ projects_cc_show_status: value });
          }}
        />

        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 1,
            alignItems: 'center',
            mb: 1,
          }}
        >
          <ToggleButtonGroup
            exclusive
            size="small"
            value={appliedFilters.layout}
            onChange={(_e, value) => {
              if (!value) return;
              setAppliedFilters((current) => ({ ...current, layout: value }));
              void updatePreferences({ projects_cc_layout: value });
            }}
            aria-label="Projects layout"
          >
            <ToggleButton value="list">List</ToggleButton>
            <ToggleButton value="card">Cards</ToggleButton>
            <ToggleButton value="grouped">Grouped</ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={appliedFilters.groupBy}
            onChange={(_e, value) => {
              if (!value) return;
              setAppliedFilters((current) => ({
                ...current,
                groupBy: value,
                groupByTeam: value === 'team',
                layout: value === 'none' ? current.layout : 'grouped',
              }));
            }}
            aria-label="Group projects by"
          >
            <ToggleButton value="none">No group</ToggleButton>
            <ToggleButton value="team">Team</ToggleButton>
            <ToggleButton value="workstream">Workstream</ToggleButton>
            <ToggleButton value="customer">Customer</ToggleButton>
            <ToggleButton value="health">Health</ToggleButton>
          </ToggleButtonGroup>
          {shouldGroupByWorkstream ? (
            <ProsohmButton
              size="small"
              buttonVariant="outlined"
              onClick={() => setWorkstreamManagerOpen(true)}
            >
              Sections
            </ProsohmButton>
          ) : null}
          {savedViews.length > 0 ? (
            <ToggleButtonGroup
              exclusive
              size="small"
              value={null}
              onChange={(_e, viewId) => {
                if (!viewId) return;
                const view = savedViews.find((item) => item.id === viewId);
                if (!view) return;
                const fj = view.filter_json ?? {};
                setAppliedFilters((current) => ({
                  ...current,
                  workstreamIds: Array.isArray(fj.workstreamIds)
                    ? (fj.workstreamIds as string[])
                    : current.workstreamIds,
                  statusBucketIds: Array.isArray(fj.statusBucketIds)
                    ? (fj.statusBucketIds as string[])
                    : current.statusBucketIds,
                  health:
                    fj.health === 'red' || fj.health === 'yellow' || fj.health === 'green'
                      ? fj.health
                      : current.health,
                  dueDate:
                    fj.dueDate === 'week' ||
                    fj.dueDate === 'overdue' ||
                    fj.dueDate === '7days' ||
                    fj.dueDate === 'all'
                      ? fj.dueDate
                      : current.dueDate,
                  search: typeof fj.search === 'string' ? fj.search : current.search,
                  layout:
                    (view.display_json?.layout as ProjectCommandCenterFilters['layout']) ??
                    current.layout,
                  groupBy:
                    (view.display_json?.groupBy as ProjectCommandCenterFilters['groupBy']) ??
                    current.groupBy,
                }));
                if (Array.isArray(fj.teamIds)) {
                  setSelectedTeamIds(fj.teamIds as string[]);
                }
              }}
              aria-label="Saved views"
            >
              {savedViews.slice(0, 6).map((view) => (
                <ToggleButton key={view.id} value={view.id}>
                  {view.name}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          ) : null}
          <ProsohmButton
            buttonVariant="outlined"
            size="small"
            onClick={() => {
              void createProjectView({
                name: `View ${new Date().toLocaleDateString()}`,
                filter_json: {
                  workstreamIds: appliedFilters.workstreamIds,
                  teamIds: selectedTeamIds,
                  statusBucketIds: appliedFilters.statusBucketIds,
                  health: appliedFilters.health,
                  dueDate: appliedFilters.dueDate,
                  search: appliedFilters.search,
                },
                display_json: {
                  layout: appliedFilters.layout,
                  groupBy: appliedFilters.groupBy,
                },
              })
                .then((view) => {
                  setSavedViews((current) => [...current, view]);
                  showSuccess('Saved view created');
                })
                .catch((error: Error) => showError(error.message));
            }}
          >
            Save view
          </ProsohmButton>
          {summaryQuery.data ? (
            <Typography variant="caption" color="text.secondary">
              Active {summaryQuery.data.active_count} · Due week {summaryQuery.data.due_week_count} ·
              Overdue {summaryQuery.data.overdue_count} · At risk {summaryQuery.data.at_risk_count}
              {summaryQuery.data.estimated_hours
                ? ` · Hours ${summaryQuery.data.actual_hours}/${summaryQuery.data.estimated_hours}`
                : ''}
            </Typography>
          ) : null}
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
              <ToggleButton value="my_streams">My streams</ToggleButton>
              <ToggleButton value="my_teams">My teams</ToggleButton>
              {allowAllScope ? <ToggleButton value="all">All</ToggleButton> : null}
            </ToggleButtonGroup>
          </FilterToolbar>

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

        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', lg: 'row' },
            alignItems: 'flex-start',
            gap: 1.5,
          }}
        >
          <Box sx={{ flex: 1, minWidth: 0, width: '100%' }}>
          {tableLoading ? (
            <TableSkeleton rows={8} columns={8} />
          ) : !displayLiveProjects.length && !completedProjects.length ? (
            <EmptyState
              title="No projects found"
              description={
                showCreateProject
                  ? 'Try adjusting your search, stream scope, or filters, or create a new project.'
                  : 'Try adjusting your search, stream scope, or filters.'
              }
            />
          ) : (
            <>
              {teamScopedLiveProjects.length ? (
                shouldGroupByWorkstream ? (
                  liveWorkstreamGroups.map((group) => (
                    <ProjectWorkstreamSection
                      key={group.id}
                      group={group}
                      customers={customersQuery.data ?? []}
                      users={usersQuery.data ?? []}
                      streams={streamsQuery.data ?? []}
                      teams={teamsQuery.data ?? []}
                      pinned={workstreamPrefs.pinned.includes(group.id)}
                      collapsed={workstreamPrefs.collapsed[group.id] === true}
                      onCollapsedChange={(collapsed) => {
                        updateWorkstreamPrefs({
                          ...workstreamPrefs,
                          collapsed: {
                            ...workstreamPrefs.collapsed,
                            ...(collapsed
                              ? { [group.id]: true }
                              : (() => {
                                  const next = { ...workstreamPrefs.collapsed };
                                  delete next[group.id];
                                  return next;
                                })()),
                          },
                        });
                      }}
                      onTogglePin={(workstreamId) => {
                        const pinned = workstreamPrefs.pinned.includes(workstreamId)
                          ? workstreamPrefs.pinned.filter((id) => id !== workstreamId)
                          : [...workstreamPrefs.pinned, workstreamId];
                        updateWorkstreamPrefs({ ...workstreamPrefs, pinned });
                      }}
                      onHide={(workstreamId) => {
                        updateWorkstreamPrefs({
                          ...workstreamPrefs,
                          hidden: workstreamPrefs.hidden.includes(workstreamId)
                            ? workstreamPrefs.hidden
                            : [...workstreamPrefs.hidden, workstreamId],
                        });
                      }}
                      gridSessionKey={gridSessionKey}
                      onRowOpen={(row) => navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)}
                      onEdit={handleEdit}
                      onArchive={showArchiveActions ? setArchiveId : undefined}
                      onDuplicate={handleDuplicate}
                      onExport={handleExport}
                      onDelete={canDelete ? setDeleteId : undefined}
                      canDelete={canDelete}
                    />
                  ))
                ) : shouldGroupByStream ? (
                  visibleStreamSections.map((streamSection) => {
                    const teamGroupsWithProjects = streamSection.teamGroups.filter(
                      (group) => group.projects.length > 0,
                    );
                    const flatProjects = teamGroupsWithProjects.flatMap((group) => group.projects);
                    const useTeamNesting =
                      shouldGroupLiveProjectsByTeam && teamGroupsWithProjects.length > 1;

                    return (
                      <ProjectStreamPanel
                        key={streamSection.streamId ?? 'unassigned'}
                        streamName={streamSection.streamName}
                        projectCount={streamSection.projectCount}
                        showChrome={showStreamChrome}
                        defaultExpanded
                      >
                        {useTeamNesting ? (
                          teamGroupsWithProjects.map((group) => (
                            <ProjectListSection
                              key={`${streamSection.streamId ?? 'unassigned'}-${group.teamId ?? 'unassigned'}`}
                              title={group.teamName}
                              count={group.projects.length}
                              projects={group.projects}
                              nested={showStreamChrome}
                              primary
                              customers={customersQuery.data ?? []}
                              users={usersQuery.data ?? []}
                              streams={streamsQuery.data ?? []}
                              teams={teamsQuery.data ?? []}
                              gridSessionKey={gridSessionKey}
                              onRowOpen={(row) =>
                                navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)
                              }
                              onEdit={handleEdit}
                              onArchive={showArchiveActions ? setArchiveId : undefined}
                              onDuplicate={handleDuplicate}
                              onExport={handleExport}
                              onDelete={canDelete ? setDeleteId : undefined}
                              canDelete={canDelete}
                            />
                          ))
                        ) : (
                          <ProjectListSection
                            title=""
                            count={flatProjects.length}
                            projects={flatProjects}
                            nested={false}
                            primary
                            customers={customersQuery.data ?? []}
                            users={usersQuery.data ?? []}
                            streams={streamsQuery.data ?? []}
                            teams={teamsQuery.data ?? []}
                            gridSessionKey={gridSessionKey}
                            onRowOpen={(row) =>
                              navigateWithBack(navigate, `/projects/${row.id}?tab=milestones`)
                            }
                            onEdit={handleEdit}
                            onArchive={showArchiveActions ? setArchiveId : undefined}
                            onDuplicate={handleDuplicate}
                            onExport={handleExport}
                            onDelete={canDelete ? setDeleteId : undefined}
                            canDelete={canDelete}
                          />
                        )}
                      </ProjectStreamPanel>
                    );
                  })
                ) : shouldGroupByCustomer ? (
                  liveCustomerGroups.map((group) => (
                    <ProjectListSection
                      key={group.id}
                      title={group.label}
                      count={group.projects.length}
                      projects={group.projects}
                      primary
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
                  ))
                ) : shouldGroupByHealth ? (
                  liveHealthGroups.map((group) => (
                    <ProjectListSection
                      key={group.id}
                      title={group.label}
                      count={group.projects.length}
                      projects={group.projects}
                      primary
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
                      onEdit={handleEdit}
                      onArchive={showArchiveActions ? setArchiveId : undefined}
                      onDuplicate={handleDuplicate}
                      onExport={handleExport}
                      onDelete={canDelete ? setDeleteId : undefined}
                      canDelete={canDelete}
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
                              onEdit={handleEdit}
                    onArchive={showArchiveActions ? setArchiveId : undefined}
                              onDuplicate={handleDuplicate}
                    onExport={handleExport}
                    onDelete={canDelete ? setDeleteId : undefined}
                    canDelete={canDelete}
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
                              onEdit={handleEdit}
                              onDuplicate={handleDuplicate}
                  onExport={handleExport}
                />
              ) : null}
            </>
          )}
          </Box>

          <Box
            sx={{
              width: { xs: '100%', lg: 'auto' },
              order: { xs: -1, lg: 0 },
            }}
          >
            <ProjectTeamFilterRail
              options={teamFilterOptions}
              selectedIds={selectedTeamIds}
              onChange={setSelectedTeamIds}
            />
          </Box>
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

      <WorkstreamSectionsManager
        open={workstreamManagerOpen}
        onClose={() => setWorkstreamManagerOpen(false)}
        catalog={workstreamsQuery.data ?? []}
        prefs={workstreamPrefs}
        onChange={updateWorkstreamPrefs}
      />
    </PageContainer>
  );
}
