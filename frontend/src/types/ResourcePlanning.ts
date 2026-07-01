import type { TeamResourcePlanningRow } from './Team';

export type ResourcePlanningGranularity = 'day' | 'week' | 'month';

export type ResourceStatusColor = 'green' | 'blue' | 'orange' | 'red' | 'grey';

export interface ResourceAllocationBlock {
  project_id: string;
  tool_number: string;
  customer_name: string;
  milestone_name: string | null;
  hours: number;
  status_color: ResourceStatusColor;
}

export interface ResourcePlanningPeriod {
  key: string;
  label: string;
  start_date: string;
  end_date: string;
}

export interface ResourcePlanningCell {
  period_key: string;
  capacity_hours: number;
  allocated_hours: number;
  remaining_hours: number;
  status_color: ResourceStatusColor;
  blocks: ResourceAllocationBlock[];
}

export interface ResourcePlanningDesignerRow {
  user_id: string;
  designer_name: string;
  team_name: string | null;
  availability_status: string;
  capacity_hours: number;
  allocated_hours: number;
  remaining_hours: number;
  cells: ResourcePlanningCell[];
}

export interface UnassignedProjectBlock {
  project_id: string;
  tool_number: string;
  customer_name: string;
  quoted_hours: number;
  remaining_hours: number;
  due_date: string;
  milestone_name: string | null;
}

export interface ResourcePlanningGrid {
  granularity: ResourcePlanningGranularity;
  start_date: string;
  end_date: string;
  periods: ResourcePlanningPeriod[];
  designers: ResourcePlanningDesignerRow[];
  unassigned_projects: UnassignedProjectBlock[];
  team_summary: TeamResourcePlanningRow[];
}
