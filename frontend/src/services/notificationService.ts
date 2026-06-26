import { apiClient } from '../api/client';
import type { Activity, Notification, NotificationSummary, WorkflowDashboard } from '../types';

export const notificationQueryKeys = {
  all: ['notifications'] as const,
  summary: ['notifications', 'summary'] as const,
};

export const activityQueryKeys = {
  all: ['activities'] as const,
  project: (projectId: string) => ['activities', 'project', projectId] as const,
};

export async function getNotifications(unreadOnly = false): Promise<Notification[]> {
  const { data } = await apiClient.get<Notification[]>('/notifications', {
    params: unreadOnly ? { unread_only: true } : undefined,
  });
  return data;
}

export async function getNotificationSummary(): Promise<NotificationSummary> {
  const { data } = await apiClient.get<NotificationSummary>('/notifications/summary');
  return data;
}

export async function markNotificationRead(notificationId: string): Promise<Notification> {
  const { data } = await apiClient.post<Notification>(
    `/notifications/${notificationId}/read`,
  );
  return data;
}

export async function markAllNotificationsRead(): Promise<NotificationSummary> {
  const { data } = await apiClient.post<NotificationSummary>('/notifications/read-all');
  return data;
}

export async function getProjectActivities(projectId: string): Promise<Activity[]> {
  const { data } = await apiClient.get<Activity[]>(`/activities/project/${projectId}`);
  return data;
}

export async function getWorkflowDashboard(): Promise<WorkflowDashboard> {
  const { data } = await apiClient.get<WorkflowDashboard>('/dashboard/workflow');
  return data;
}
