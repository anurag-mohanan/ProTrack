import type { Customer, Project, Team, User } from '../types';
import type { ExecutionStatus, ProjectStage, ProjectHealth } from '../types/common';
import { PROJECT_STAGE_LABELS } from '../types/common';
import { formatCellValue, userDisplayName } from './format';

export type ProjectQuickFilter =
  | 'none'
  | 'active'
  | 'in_progress'
  | 'on_hold'
  | 'overdue'
  | 'due_week'
  | 'completed_month'
  | 'archived'
  | 'not_started';

export type ProjectDueFilter = 'all' | 'week' | '7days' | 'overdue';

export type ProjectPriorityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

export interface ProjectCommandCenterFilters {
  search: string;
  customerIds: string[];
  projectTypeId: string;
  teamIds: string[];
  projectStage: ProjectStage | 'all';
  executionStatus: ExecutionStatus | 'all';
  designLeaderId: string;
  designerId: string;
  surfacerId: string;
  priority: ProjectPriorityFilter;
  health: ProjectHealth | 'all';
  dueDate: ProjectDueFilter;
  showArchived: boolean;
  groupByTeam: boolean;
  quickFilter: ProjectQuickFilter;
  customerId?: string;
  designerUserId?: string;
}

export const defaultProjectCommandCenterFilters: ProjectCommandCenterFilters = {
  search: '',
  customerIds: [],
  projectTypeId: 'all',
  teamIds: [],
  projectStage: 'all',
  executionStatus: 'all',
  designLeaderId: 'all',
  designerId: 'all',
  surfacerId: 'all',
  priority: 'all',
  health: 'all',
  dueDate: 'all',
  showArchived: false,
  groupByTeam: false,
  quickFilter: 'none',
};

const PRIORITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export function formatProjectStageDisplay(project: Project): string {
  if (project.is_archived) return 'Archived';
  if (project.execution_status === 'completed') return 'Completed';
  if (project.execution_status === 'cancelled') return 'Cancelled';
  return PROJECT_STAGE_LABELS[project.project_stage] ?? '—';
}

export function formatExecutionStatusShort(status: ExecutionStatus): string {
  const labels: Record<ExecutionStatus, string> = {
    planning: 'Planning',
    currently_being_worked_on: 'In Progress',
    on_hold: 'On Hold',
    cancelled: 'Cancelled',
    completed: 'Completed',
  };
  return labels[status];
}

export function isLiveProject(project: Project): boolean {
  if (project.is_deleted || project.is_archived) return false;
  return project.execution_status !== 'completed' && project.execution_status !== 'cancelled';
}

export function isCompletedProject(project: Project): boolean {
  if (project.is_deleted || project.is_archived) return false;
  return project.execution_status === 'completed';
}

export function isArchivedProject(project: Project): boolean {
  return Boolean(project.is_archived) && !project.is_deleted;
}

function isOverdue(project: Project, today: Date): boolean {
  if (!isLiveProject(project) || !project.due_date) return false;
  return new Date(`${project.due_date}T00:00:00`) < today;
}

function isDueThisWeek(project: Project, today: Date): boolean {
  if (!isLiveProject(project) || !project.due_date) return false;
  const rangeStart = new Date(today);
  const day = rangeStart.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  rangeStart.setDate(rangeStart.getDate() + diff);
  const rangeEnd = new Date(rangeStart);
  rangeEnd.setDate(rangeEnd.getDate() + 6);
  const due = new Date(`${project.due_date}T00:00:00`);
  return due >= rangeStart && due <= rangeEnd;
}

function isDueNext7Days(project: Project, today: Date): boolean {
  if (!project.due_date || project.execution_status === 'completed') return false;
  const rangeEnd = new Date(today);
  rangeEnd.setDate(rangeEnd.getDate() + 7);
  const due = new Date(`${project.due_date}T00:00:00`);
  return due >= today && due <= rangeEnd;
}

function isCompletedThisMonth(project: Project, today: Date): boolean {
  if (project.execution_status !== 'completed' || !project.completed_at) return false;
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const completed = new Date(project.completed_at);
  return completed >= monthStart && completed <= today;
}

function isNotStarted(project: Project): boolean {
  return (
    project.execution_status === 'currently_being_worked_on' &&
    Number(project.progress_percent ?? 0) <= 0
  );
}

function matchesDueFilter(project: Project, dueDate: ProjectDueFilter, today: Date): boolean {
  if (dueDate === 'all') return true;
  if (dueDate === 'overdue') return isOverdue(project, today);
  if (dueDate === 'week') return isDueThisWeek(project, today);
  if (dueDate === '7days') return isDueNext7Days(project, today);
  return true;
}

function matchesQuickFilter(project: Project, quickFilter: ProjectQuickFilter, today: Date): boolean {
  switch (quickFilter) {
    case 'none':
      return true;
    case 'active':
      return isLiveProject(project);
    case 'in_progress':
      return project.execution_status === 'currently_being_worked_on' && isLiveProject(project);
    case 'on_hold':
      return project.execution_status === 'on_hold';
    case 'overdue':
      return isOverdue(project, today);
    case 'due_week':
      return isDueThisWeek(project, today);
    case 'completed_month':
      return isCompletedThisMonth(project, today);
    case 'archived':
      return isArchivedProject(project);
    case 'not_started':
      return isNotStarted(project);
    default:
      return true;
  }
}

export function buildProjectSearchHaystack(
  project: Project,
  lookup: {
    customerName?: string;
    teamName?: string;
    designLeaderName?: string;
    designerName?: string;
  },
): string {
  return [
    project.tool_number,
    project.part_description,
    project.code,
    lookup.customerName,
    lookup.teamName,
    lookup.designLeaderName,
    lookup.designerName,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

export function filterProjectsForCommandCenter(
  projects: Project[],
  filters: ProjectCommandCenterFilters,
  lookup: {
    customers: Customer[];
    teams: Team[];
    users: User[];
  },
): Project[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const customerMap = new Map(lookup.customers.map((item) => [item.id, item.name]));
  const teamMap = new Map(lookup.teams.map((item) => [item.id, item.name]));
  const userMap = new Map(lookup.users.map((item) => [item.id, userDisplayName(item)]));

  const term = filters.search.trim().toLowerCase();
  const customerFilterIds = filters.customerId
    ? [filters.customerId]
    : filters.customerIds;

  return projects.filter((project) => {
    if (project.is_deleted) return false;

    if (filters.showArchived || filters.quickFilter === 'archived') {
      if (!isArchivedProject(project)) return false;
    } else if (isArchivedProject(project)) {
      return false;
    }

    if (customerFilterIds.length > 0 && !customerFilterIds.includes(project.customer_id)) {
      return false;
    }

    if (filters.teamIds.length > 0) {
      if (!project.team_id || !filters.teamIds.includes(project.team_id)) return false;
    }

    if (filters.projectStage !== 'all' && project.project_stage !== filters.projectStage) {
      return false;
    }

    if (filters.executionStatus !== 'all' && project.execution_status !== filters.executionStatus) {
      return false;
    }

    if (filters.designLeaderId !== 'all' && project.design_leader_id !== filters.designLeaderId) {
      return false;
    }

    if (filters.designerId !== 'all') {
      if (!project.designer_id || project.designer_id !== filters.designerId) return false;
    }

    if (filters.designerUserId) {
      const assigned =
        project.designer_id === filters.designerUserId ||
        project.design_leader_id === filters.designerUserId;
      if (!assigned) return false;
    }

    if (filters.surfacerId !== 'all') {
      if (!project.surfacer_id || project.surfacer_id !== filters.surfacerId) return false;
    }

    if (filters.priority !== 'all' && (project.priority ?? 'medium') !== filters.priority) {
      return false;
    }

    if (filters.health !== 'all' && project.health !== filters.health) {
      return false;
    }

    if (!matchesDueFilter(project, filters.dueDate, today)) return false;
    if (!matchesQuickFilter(project, filters.quickFilter, today)) return false;

    if (term) {
      const haystack = buildProjectSearchHaystack(project, {
        customerName: formatCellValue(customerMap.get(project.customer_id)),
        teamName: project.team_id ? formatCellValue(teamMap.get(project.team_id)) : '',
        designLeaderName: project.design_leader_id
          ? formatCellValue(userMap.get(project.design_leader_id))
          : '',
        designerName: project.designer_id ? formatCellValue(userMap.get(project.designer_id)) : '',
      });
      if (!haystack.includes(term)) return false;
    }

    return true;
  });
}

export function sortLiveProjects(projects: Project[]): Project[] {
  return [...projects].sort((a, b) => {
    const dueA = a.due_date ? new Date(`${a.due_date}T00:00:00`).getTime() : Number.MAX_SAFE_INTEGER;
    const dueB = b.due_date ? new Date(`${b.due_date}T00:00:00`).getTime() : Number.MAX_SAFE_INTEGER;
    if (dueA !== dueB) return dueA - dueB;

    const priorityA = PRIORITY_ORDER[a.priority ?? 'medium'] ?? 2;
    const priorityB = PRIORITY_ORDER[b.priority ?? 'medium'] ?? 2;
    if (priorityA !== priorityB) return priorityA - priorityB;

    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });
}

export function sortCompletedProjects(projects: Project[]): Project[] {
  return [...projects].sort((a, b) => {
    const completedA = a.completed_at ? new Date(a.completed_at).getTime() : 0;
    const completedB = b.completed_at ? new Date(b.completed_at).getTime() : 0;
    return completedB - completedA;
  });
}

export function sortProjectsByTeam(
  projects: Project[],
  teams: Team[],
): Project[] {
  const teamMap = new Map(teams.map((team) => [team.id, team.name]));
  return [...projects].sort((a, b) => {
    const teamA = a.team_id ? (teamMap.get(a.team_id) ?? 'Unassigned') : 'Unassigned';
    const teamB = b.team_id ? (teamMap.get(b.team_id) ?? 'Unassigned') : 'Unassigned';
    return teamA.localeCompare(teamB) || a.tool_number.localeCompare(b.tool_number);
  });
}

export function countLiveProjects(projects: Project[]): number {
  return projects.filter(isLiveProject).length;
}

export function countByExecutionStatus(
  projects: Project[],
  status: ExecutionStatus,
): number {
  return projects.filter((project) => project.execution_status === status && isLiveProject(project)).length;
}

export function countOverdueProjects(projects: Project[]): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return projects.filter((project) => isOverdue(project, today)).length;
}

export function countDueThisWeekProjects(projects: Project[]): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return projects.filter((project) => isDueThisWeek(project, today)).length;
}

export function countNotStartedProjects(projects: Project[]): number {
  return projects.filter((project) => isNotStarted(project) && isLiveProject(project)).length;
}

export interface ProjectPortfolioMetrics {
  liveCount: number;
  inProgressCount: number;
  onHoldCount: number;
  planningCount: number;
  overdueCount: number;
  dueThisWeekCount: number;
  notStartedCount: number;
  completedThisMonthCount: number;
  quotedHours: number;
  actualHours: number;
}

export function countCompletedThisMonthProjects(projects: Project[]): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return projects.filter((project) => isCompletedThisMonth(project, today)).length;
}

function sumLiveHours(projects: Project[], field: 'quoted_hours' | 'actual_hours'): number {
  return projects
    .filter(isLiveProject)
    .reduce((total, project) => total + Number(project[field] ?? 0), 0);
}

/** Single source of truth for Projects command-center KPIs and chips. */
export function computeProjectPortfolioMetrics(projects: Project[]): ProjectPortfolioMetrics {
  return {
    liveCount: countLiveProjects(projects),
    inProgressCount: countByExecutionStatus(projects, 'currently_being_worked_on'),
    onHoldCount: countByExecutionStatus(projects, 'on_hold'),
    planningCount: countByExecutionStatus(projects, 'planning'),
    overdueCount: countOverdueProjects(projects),
    dueThisWeekCount: countDueThisWeekProjects(projects),
    notStartedCount: countNotStartedProjects(projects),
    completedThisMonthCount: countCompletedThisMonthProjects(projects),
    quotedHours: sumLiveHours(projects, 'quoted_hours'),
    actualHours: sumLiveHours(projects, 'actual_hours'),
  };
}

export function countActiveSidebarFilters(filters: ProjectCommandCenterFilters): number {
  let count = 0;
  if (filters.customerIds.length > 0) count += 1;
  if (filters.projectTypeId !== 'all') count += 1;
  if (filters.teamIds.length > 0) count += 1;
  if (filters.projectStage !== 'all') count += 1;
  if (filters.executionStatus !== 'all') count += 1;
  if (filters.designLeaderId !== 'all') count += 1;
  if (filters.designerId !== 'all') count += 1;
  if (filters.surfacerId !== 'all') count += 1;
  if (filters.priority !== 'all') count += 1;
  if (filters.health !== 'all') count += 1;
  if (filters.dueDate !== 'all') count += 1;
  if (filters.showArchived) count += 1;
  return count;
}

export interface ProjectFilterChipDef {
  key: string;
  label: string;
  patch: (current: ProjectCommandCenterFilters) => ProjectCommandCenterFilters;
}

interface ProjectFilterChipLookup {
  customerNameMap: Map<string, string>;
  teamNameMap: Map<string, string>;
  userNameMap: Map<string, string>;
  projectTypeNameMap: Map<string, string>;
}

export function getProjectActiveFilterChips(
  filters: ProjectCommandCenterFilters,
  lookup: ProjectFilterChipLookup,
): ProjectFilterChipDef[] {
  const chips: ProjectFilterChipDef[] = [];

  filters.customerIds.forEach((id) => {
    chips.push({
      key: `customer-${id}`,
      label: `Customer: ${lookup.customerNameMap.get(id) ?? 'Unknown'}`,
      patch: (current) => ({
        ...current,
        customerIds: current.customerIds.filter((value) => value !== id),
      }),
    });
  });

  filters.teamIds.forEach((id) => {
    chips.push({
      key: `team-${id}`,
      label: `Team: ${lookup.teamNameMap.get(id) ?? 'Unknown'}`,
      patch: (current) => ({
        ...current,
        teamIds: current.teamIds.filter((value) => value !== id),
      }),
    });
  });

  if (filters.projectStage !== 'all') {
    chips.push({
      key: 'stage',
      label: `Stage: ${filters.projectStage.replaceAll('_', ' ')}`,
      patch: (current) => ({ ...current, projectStage: 'all' }),
    });
  }

  if (filters.executionStatus !== 'all') {
    chips.push({
      key: 'status',
      label: `Status: ${formatExecutionStatusShort(filters.executionStatus)}`,
      patch: (current) => ({ ...current, executionStatus: 'all' }),
    });
  }

  if (filters.designerId !== 'all') {
    chips.push({
      key: 'designer',
      label: `Designer: ${lookup.userNameMap.get(filters.designerId) ?? 'Unknown'}`,
      patch: (current) => ({ ...current, designerId: 'all' }),
    });
  }

  if (filters.projectTypeId !== 'all') {
    chips.push({
      key: 'project-type',
      label: `Type: ${lookup.projectTypeNameMap.get(filters.projectTypeId) ?? 'Unknown'}`,
      patch: (current) => ({ ...current, projectTypeId: 'all' }),
    });
  }

  if (filters.designLeaderId !== 'all') {
    chips.push({
      key: 'design-leader',
      label: `Leader: ${lookup.userNameMap.get(filters.designLeaderId) ?? 'Unknown'}`,
      patch: (current) => ({ ...current, designLeaderId: 'all' }),
    });
  }

  if (filters.surfacerId !== 'all') {
    chips.push({
      key: 'surfacer',
      label: `Surfacer: ${lookup.userNameMap.get(filters.surfacerId) ?? 'Unknown'}`,
      patch: (current) => ({ ...current, surfacerId: 'all' }),
    });
  }

  if (filters.priority !== 'all') {
    chips.push({
      key: 'priority',
      label: `Priority: ${filters.priority}`,
      patch: (current) => ({ ...current, priority: 'all' }),
    });
  }

  if (filters.health !== 'all') {
    chips.push({
      key: 'health',
      label: `Health: ${filters.health}`,
      patch: (current) => ({ ...current, health: 'all' }),
    });
  }

  if (filters.dueDate !== 'all') {
    const dueLabels: Record<ProjectDueFilter, string> = {
      all: 'Any',
      week: 'Due this week',
      '7days': 'Due next 7 days',
      overdue: 'Overdue',
    };
    chips.push({
      key: 'due-date',
      label: dueLabels[filters.dueDate],
      patch: (current) => ({ ...current, dueDate: 'all' }),
    });
  }

  if (filters.showArchived) {
    chips.push({
      key: 'archived',
      label: 'Archived',
      patch: (current) => ({ ...current, showArchived: false }),
    });
  }

  return chips;
}

/** Apply a KPI / quick-filter chip selection with consistent, non-stale filter state. */
export function applyKpiQuickFilter(
  current: ProjectCommandCenterFilters,
  filter: ProjectQuickFilter,
): ProjectCommandCenterFilters {
  if (filter === 'none') {
    return {
      ...current,
      quickFilter: 'none',
      showArchived: false,
      dueDate: 'all',
    };
  }

  const next: ProjectCommandCenterFilters = {
    ...current,
    quickFilter: filter,
    showArchived: filter === 'archived',
    dueDate: 'all',
  };

  if (filter === 'overdue') {
    return { ...next, dueDate: 'overdue' };
  }
  if (filter === 'due_week') {
    return { ...next, dueDate: 'week' };
  }

  return next;
}
