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

export async function fetchEngineeringCalendar(): Promise<CalendarEvent[]> {
  const { data } = await apiClient.get<CalendarEvent[]>('/calendar/engineering');
  return data;
}
