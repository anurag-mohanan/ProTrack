import { apiClient } from './client';
import type {
  AiInsight,
  AiOperationsSummary,
  ChatResponse,
  ExecutiveWallData,
  KnowledgeRecord,
  MorningBrief,
  QuoteRecommendation,
  ResourceOptimizationResult,
  SchedulePrediction,
  TimesheetSuggestion,
} from '../types/Ai';

export async function fetchAiOperations(): Promise<AiOperationsSummary> {
  const { data } = await apiClient.get<AiOperationsSummary>('/ai/operations');
  return data;
}

export async function fetchAiInsights(limit = 10): Promise<AiInsight[]> {
  const { data } = await apiClient.get<AiInsight[]>('/ai/insights', { params: { limit } });
  return data;
}

export async function fetchMorningBrief(): Promise<MorningBrief> {
  const { data } = await apiClient.get<MorningBrief>('/ai/morning-brief');
  return data;
}

export async function fetchQuoteRecommendation(projectId: string): Promise<QuoteRecommendation> {
  const { data } = await apiClient.get<QuoteRecommendation>(`/ai/quote/${projectId}`);
  return data;
}

export async function fetchResourceRecommendations(
  projectId?: string,
): Promise<ResourceOptimizationResult> {
  const { data } = await apiClient.get<ResourceOptimizationResult>('/ai/resources', {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
}

export async function fetchSchedulePredictions(
  projectId?: string,
): Promise<SchedulePrediction[]> {
  const { data } = await apiClient.get<SchedulePrediction[]>('/ai/schedule', {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
}

export async function searchKnowledgeBase(query = ''): Promise<KnowledgeRecord[]> {
  const { data } = await apiClient.get<KnowledgeRecord[]>('/ai/knowledge', {
    params: { query },
  });
  return data;
}

export async function fetchTimesheetSuggestions(): Promise<TimesheetSuggestion[]> {
  const { data } = await apiClient.get<TimesheetSuggestion[]>('/ai/timesheet-suggestions');
  return data;
}

export async function sendAiChat(question: string): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>('/ai/chat', {
    role: 'user',
    content: question,
  });
  return data;
}

export async function fetchExecutiveWall(): Promise<ExecutiveWallData> {
  const { data } = await apiClient.get<ExecutiveWallData>('/ai/executive-wall');
  return data;
}

export const aiQueryKeys = {
  operations: ['ai', 'operations'] as const,
  insights: (limit?: number) => ['ai', 'insights', limit ?? 10] as const,
  morningBrief: ['ai', 'morning-brief'] as const,
  quote: (projectId: string) => ['ai', 'quote', projectId] as const,
  resources: (projectId?: string) => ['ai', 'resources', projectId ?? 'all'] as const,
  schedule: (projectId?: string) => ['ai', 'schedule', projectId ?? 'all'] as const,
  knowledge: (query: string) => ['ai', 'knowledge', query] as const,
  timesheetSuggestions: ['ai', 'timesheet-suggestions'] as const,
  executiveWall: ['ai', 'executive-wall'] as const,
};
