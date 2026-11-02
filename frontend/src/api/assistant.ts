import { apiClient } from './client';

export type AssistantMode = 'disabled' | 'offline' | 'llm';
export type MessageStatus = 'ok' | 'data' | 'offline' | 'error';
export type RecommendationStatus = 'new' | 'accepted' | 'rejected' | 'deferred' | 'completed';

export interface AssistantStatus {
  enabled: boolean;
  configured: boolean;
  mode: AssistantMode;
  provider: string | null;
  model: string | null;
  message: string | null;
  capabilities: Record<'projects' | 'resources' | 'finance' | 'management', boolean>;
  limits: { max_input_chars: number; questions_per_minute: number };
  streaming: boolean;
}

export interface AssistantSuggestion {
  id: string;
  category: string;
  text: string;
}

export interface AssistantSource {
  key: string;
  kind: string;
  ref: string;
  label: string;
  detail: string | null;
  route: string | null;
}

export interface AssistantTable {
  title: string;
  columns: string[];
  rows: Array<Array<string | number | boolean | null>>;
}

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status: MessageStatus;
  error_code: string | null;
  sources: AssistantSource[];
  tables: AssistantTable[];
  limitations: string[];
  follow_ups: string[];
  tool_calls: Array<{ tool: string; status: string; record_count: number | null }>;
  provider: string | null;
  model: string | null;
  feedback: 'up' | 'down' | null;
  feedback_comment: string | null;
  created_at: string;
  recommendations: Array<{ id: string; title: string; status: RecommendationStatus; priority: string }>;
}

export interface AssistantConversation {
  id: string;
  title: string;
  module: string | null;
  project_id: string | null;
  created_at: string;
  last_message_at: string | null;
  message_count: number | null;
}

export interface AssistantConversationDetail extends AssistantConversation {
  messages: AssistantMessage[];
}

export interface AssistantRecommendation {
  id: string;
  title: string;
  description: string;
  module: string;
  category: string;
  priority: string;
  status: RecommendationStatus;
  project_id: string | null;
  project_label: string | null;
  evidence: AssistantSource[];
  suggested_action: string | null;
  suggested_owner: string | null;
  conversation_id: string | null;
  created_at: string;
  created_by: string | null;
  decided_by: string | null;
  decided_at: string | null;
  completed_by: string | null;
  completed_at: string | null;
  resolution_notes: string | null;
  feedback: string | null;
  workflow_route: string | null;
  allowed_transitions: Array<Exclude<RecommendationStatus, 'new'>>;
}

export interface RecommendationPage {
  items: AssistantRecommendation[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchAssistantStatus(): Promise<AssistantStatus> {
  const { data } = await apiClient.get<AssistantStatus>('/assistant/status');
  return data;
}

export async function fetchAssistantSuggestions(): Promise<AssistantSuggestion[]> {
  const { data } = await apiClient.get<AssistantSuggestion[]>('/assistant/suggestions');
  return data;
}

export async function fetchConversations(): Promise<AssistantConversation[]> {
  const { data } = await apiClient.get<AssistantConversation[]>('/assistant/conversations');
  return data;
}

export async function fetchConversation(id: string): Promise<AssistantConversationDetail> {
  const { data } = await apiClient.get<AssistantConversationDetail>(`/assistant/conversations/${id}`);
  return data;
}

export async function createConversation(title?: string): Promise<AssistantConversation> {
  const { data } = await apiClient.post<AssistantConversation>('/assistant/conversations', { title: title ?? null });
  return data;
}

export async function renameConversation(id: string, title: string): Promise<AssistantConversation> {
  const { data } = await apiClient.patch<AssistantConversation>(`/assistant/conversations/${id}`, { title });
  return data;
}

export async function deleteConversation(id: string): Promise<void> {
  await apiClient.delete(`/assistant/conversations/${id}`);
}

export async function sendAssistantMessage(
  conversationId: string,
  content: string,
  suggestionId?: string,
): Promise<AssistantMessage> {
  const { data } = await apiClient.post<AssistantMessage>(`/assistant/conversations/${conversationId}/messages`, {
    content,
    suggestion_id: suggestionId ?? null,
  });
  return data;
}

export async function sendMessageFeedback(messageId: string, rating: 'up' | 'down' | null, comment?: string) {
  const { data } = await apiClient.post(`/assistant/messages/${messageId}/feedback`, {
    rating,
    comment: comment || null,
  });
  return data as { id: string; feedback: 'up' | 'down' | null; feedback_comment: string | null };
}

export async function fetchRecommendations(params: {
  status?: RecommendationStatus;
  page: number;
  page_size: number;
}): Promise<RecommendationPage> {
  const { data } = await apiClient.get<RecommendationPage>('/assistant/recommendations', {
    params: params.status ? params : { page: params.page, page_size: params.page_size },
  });
  return data;
}

export async function decideRecommendation(
  id: string,
  status: Exclude<RecommendationStatus, 'new'>,
  note?: string,
): Promise<AssistantRecommendation> {
  const { data } = await apiClient.patch<AssistantRecommendation>(`/assistant/recommendations/${id}`, {
    status,
    note: note || null,
  });
  return data;
}

export const assistantQueryKeys = {
  status: ['assistant', 'status'] as const,
  suggestions: ['assistant', 'suggestions'] as const,
  conversations: ['assistant', 'conversations'] as const,
  conversation: (id: string) => ['assistant', 'conversation', id] as const,
  recommendations: (status?: string, page = 1) => ['assistant', 'recommendations', status ?? 'all', page] as const,
};
