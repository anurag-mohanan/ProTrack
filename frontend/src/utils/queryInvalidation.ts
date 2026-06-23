import type { QueryClient } from '@tanstack/react-query';
import { reportQueryKeys } from '../services/reportService';
import { projectQueryKeys } from '../services/projectService';

export const milestoneQueryKeys = {
  all: ['milestones'] as const,
  byProject: (projectId: string) => ['milestones', projectId] as const,
};

export function invalidateMilestoneRelatedQueries(
  queryClient: QueryClient,
  projectId: string,
) {
  void queryClient.invalidateQueries({
    queryKey: milestoneQueryKeys.byProject(projectId),
  });
  void queryClient.invalidateQueries({
    queryKey: projectQueryKeys.detail(projectId),
  });
  void queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
  void queryClient.invalidateQueries({ queryKey: reportQueryKeys.all });
  void queryClient.invalidateQueries({ queryKey: reportQueryKeys.projectHours });
  void queryClient.invalidateQueries({ queryKey: reportQueryKeys.customerSummary });
}
