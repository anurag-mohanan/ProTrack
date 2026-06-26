import type { QueryClient } from '@tanstack/react-query';
import { reportQueryKeys } from '../services/reportService';
import { projectQueryKeys } from '../services/projectService';
import { timesheetQueryKeys } from '../services/timesheetService';

export const milestoneQueryKeys = {
  all: ['milestones'] as const,
  byProject: (projectId: string) => ['milestones', projectId] as const,
};

export function invalidateProjectCalculationQueries(
  queryClient: QueryClient,
  projectId?: string,
) {
  if (projectId) {
    void queryClient.invalidateQueries({
      queryKey: projectQueryKeys.detail(projectId),
    });
    void queryClient.invalidateQueries({
      queryKey: milestoneQueryKeys.byProject(projectId),
    });
  }

  void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['projects'] });
  void queryClient.invalidateQueries({ queryKey: milestoneQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
  void queryClient.invalidateQueries({ queryKey: ['dashboard', 'workload'] });
  void queryClient.invalidateQueries({ queryKey: reportQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['reports'] });
  void queryClient.invalidateQueries({ queryKey: timesheetQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['timesheet-entries'] });
}

export function invalidateMilestoneRelatedQueries(
  queryClient: QueryClient,
  projectId: string,
) {
  invalidateProjectCalculationQueries(queryClient, projectId);
}

export function invalidateTimesheetRelatedQueries(
  queryClient: QueryClient,
  projectId?: string,
) {
  invalidateProjectCalculationQueries(queryClient, projectId);
}
