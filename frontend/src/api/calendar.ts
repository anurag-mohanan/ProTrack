import { apiClient } from './client';

export interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  category: string;
  project_id?: string | null;
  milestone_id?: string | null;
  user_id?: string | null;
}

export interface ProjectTimelineBar {
  project_id: string;
  tool_number: string;
  customer_name?: string | null;
  team_id?: string | null;
  team_name?: string | null;
  health: string;
  execution_status: string;
  designer_name?: string | null;
  surfacer_name?: string | null;
  start_date: string;
  end_date: string;
  progress_percent: number;
  due_date_missing: boolean;
}

export async function fetchEngineeringCalendar(): Promise<CalendarEvent[]> {
  const { data } = await apiClient.get<CalendarEvent[]>('/calendar/engineering');
  return data;
}

export async function fetchProjectTimeline(params?: {
  from?: string;
  to?: string;
  team_id?: string;
}): Promise<ProjectTimelineBar[]> {
  const { data } = await apiClient.get<ProjectTimelineBar[]>('/calendar/project-timeline', {
    params,
  });
  return data;
}
