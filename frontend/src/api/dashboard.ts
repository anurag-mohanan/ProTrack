import type {
  DashboardKpis,
  DashboardMyTasks,
  DashboardOverview,
  DashboardSummary,
  DesignerWorkload,
  ProjectAttentionRow,
  ProjectDashboard,
} from '../types';
import type { Activity } from '../types/Workflow';
import type { ProjectStage } from '../types';
import { apiClient, buildQuery } from './client';

export async function fetchDashboardKpis(): Promise<DashboardKpis> {
  const { data } = await apiClient.get<DashboardKpis>('/dashboard/kpis');
  return data;
}

export async function fetchAttentionProjects(): Promise<ProjectAttentionRow[]> {
  const { data } = await apiClient.get<ProjectAttentionRow[]>('/dashboard/attention-projects');
  return data;
}

export async function fetchDashboardRecentActivity(): Promise<Activity[]> {
  const { data } = await apiClient.get<Activity[]>('/dashboard/recent-activity');
  return data;
}

export async function fetchDashboardMyTasks(): Promise<DashboardMyTasks> {
  const { data } = await apiClient.get<DashboardMyTasks>('/dashboard/my-tasks');
  return data;
}

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await apiClient.get<DashboardOverview>('/dashboard/overview');
  return data;
}

export async function fetchDashboardSummary(
  projectStage?: ProjectStage,
  teamId?: string,
  teamIds?: string[],
): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>(
    `/dashboard/summary${buildQuery({
      project_stage: projectStage,
      team_id: teamId,
      team_ids: teamIds,
    })}`,
  );
  return data;
}

export interface ManagementKpis {
  projects_managed: number;
  projects_delivered: number;
  overdue_projects: number;
  pending_reviews: number;
  pending_milestone_approvals: number;
  upcoming_deliveries: number;
  timesheet_compliance_pending: number;
  team_utilization_percent?: number | null;
  high_risk_projects: number;
  teams_managed?: number;
  team_members_under?: number;
}

export interface LeadershipScopeKpis {
  teams_managed: number;
  team_members_under: number;
  show_teams_managed: boolean;
  is_team_leader: boolean;
}

export interface AdministrationKpis {
  active_users: number;
  import_queue: number;
  failed_jobs: number;
  failed_emails: number;
  backups_count: number;
  last_backup?: string | null;
  audit_actions_7d: number;
  emails_sent: number;
  backend_status: string;
  database_status: string;
}

export interface RoleKpiSnapshot {
  dashboard_profile: string;
  management?: ManagementKpis | null;
  administration?: AdministrationKpis | null;
  leadership?: LeadershipScopeKpis | null;
  engineering_productivity_user_count: number;
  capacity_planning_user_count: number;
}

export async function fetchRoleKpis(): Promise<RoleKpiSnapshot> {
  const { data } = await apiClient.get<RoleKpiSnapshot>('/dashboard/role-kpis');
  return data;
}

export async function fetchTeamResourcePlanning(teamId?: string) {
  const { data } = await apiClient.get<import('../types/Team').TeamResourcePlanningRow[]>(
    `/dashboard/resource-planning${buildQuery({ team_id: teamId })}`,
  );
  return data;
}

export async function fetchDesignerWorkload(): Promise<DesignerWorkload[]> {
  const { data } = await apiClient.get<DesignerWorkload[]>('/dashboard/workload');
  return data;
}

export async function fetchProjectDashboard(
  projectId: string,
): Promise<ProjectDashboard> {
  const { data } = await apiClient.get<ProjectDashboard>(
    `/dashboard/project/${projectId}`,
  );
  return data;
}

export async function sendTimesheetReminder(userId: string): Promise<void> {
  await apiClient.post(`/dashboard/timesheet-reminders/${userId}`);
}

export const dashboardQueryKeys = {
  all: ['dashboard'] as const,
  summary: (projectStage?: ProjectStage, teamId?: string, teamIds?: string[]) =>
    projectStage || teamId || teamIds?.length
      ? (['dashboard', 'summary', projectStage, teamId, teamIds] as const)
      : (['dashboard', 'summary'] as const),
  kpis: ['dashboard', 'kpis'] as const,
  attentionProjects: ['dashboard', 'attention-projects'] as const,
  recentActivity: ['dashboard', 'recent-activity'] as const,
  myTasks: ['dashboard', 'my-tasks'] as const,
  overview: ['dashboard', 'overview'] as const,
  roleKpis: ['dashboard', 'role-kpis'] as const,
};
