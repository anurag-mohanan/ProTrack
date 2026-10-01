import { apiClient, buildQuery, type ListParams } from './client';
import type {
  EmployeeTicketRow,
  Ticket,
  TicketAssignee,
  TicketCapabilities,
  TicketCatalog,
  TicketCategoryRoute,
  TicketCategoryRouteUpdate,
  TicketComment,
  TicketCreate,
  TicketDetail,
  TicketPage,
  TicketQueueParams,
  TicketQueueSummary,
  TicketReconciliation,
  TicketReport,
  TicketRoutingRule,
  TicketRoutingRuleWrite,
  TicketSlaPolicy,
  TicketStats,
  TicketStatusChange,
  TicketUpdate,
} from '../types/tickets';

export const ticketsApi = {
  list: async (params?: TicketQueueParams & { scope?: string }): Promise<Ticket[]> => {
    const { data } = await apiClient.get<Ticket[]>(`/tickets${buildQuery(params as ListParams)}`);
    return data;
  },
  queue: async (params: TicketQueueParams): Promise<TicketPage> => {
    const { data } = await apiClient.get<TicketPage>(`/tickets/queue${buildQuery(params as ListParams)}`);
    return data;
  },
  summary: async (category?: string): Promise<TicketQueueSummary> => {
    const { data } = await apiClient.get<TicketQueueSummary>(
      `/tickets/queue/summary${buildQuery({ category })}`,
    );
    return data;
  },
  exportCsv: async (params: TicketQueueParams): Promise<Blob> => {
    const { data } = await apiClient.get<Blob>(`/tickets/export.csv${buildQuery(params as ListParams)}`, {
      responseType: 'blob',
    });
    return data;
  },
  catalog: async (): Promise<TicketCatalog> => {
    const { data } = await apiClient.get<TicketCatalog>('/tickets/catalog');
    return data;
  },
  me: async (): Promise<TicketCapabilities> => {
    const { data } = await apiClient.get<TicketCapabilities>('/tickets/me');
    return data;
  },
  assignees: async (category: string): Promise<TicketAssignee[]> => {
    const { data } = await apiClient.get<TicketAssignee[]>(
      `/tickets/assignees${buildQuery({ category })}`,
    );
    return data;
  },
  stats: async (): Promise<TicketStats> => {
    const { data } = await apiClient.get<TicketStats>('/tickets/stats');
    return data;
  },
  get: async (id: string): Promise<TicketDetail> => {
    const { data } = await apiClient.get<TicketDetail>(`/tickets/${id}`);
    return data;
  },
  create: async (payload: TicketCreate): Promise<TicketDetail> => {
    const { data } = await apiClient.post<TicketDetail>('/tickets', payload);
    return data;
  },
  update: async (id: string, payload: TicketUpdate): Promise<TicketDetail> => {
    const { data } = await apiClient.patch<TicketDetail>(`/tickets/${id}`, payload);
    return data;
  },
  assign: async (id: string, assigneeId: string | null, reason?: string): Promise<TicketDetail> => {
    const { data } = await apiClient.post<TicketDetail>(`/tickets/${id}/assign`, {
      assignee_id: assigneeId,
      reason: reason || null,
    });
    return data;
  },
  take: async (id: string): Promise<TicketDetail> => {
    const { data } = await apiClient.post<TicketDetail>(`/tickets/${id}/take`);
    return data;
  },
  transfer: async (
    id: string,
    payload: { category: string; subcategory?: string | null; assignee_id?: string | null; reason: string },
  ): Promise<TicketDetail> => {
    const { data } = await apiClient.post<TicketDetail>(`/tickets/${id}/transfer`, payload);
    return data;
  },
  setStatus: async (id: string, payload: TicketStatusChange): Promise<TicketDetail> => {
    const { data } = await apiClient.post<TicketDetail>(`/tickets/${id}/status`, payload);
    return data;
  },
  review: async (id: string, note: string): Promise<TicketDetail> => {
    const { data } = await apiClient.post<TicketDetail>(`/tickets/${id}/review`, { note });
    return data;
  },
  retryNotifications: async (id: string): Promise<{ sent: number }> => {
    const { data } = await apiClient.post<{ sent: number }>(`/tickets/${id}/notifications/retry`);
    return data;
  },
  addComment: async (id: string, body: string, isInternal = false): Promise<TicketComment> => {
    const { data } = await apiClient.post<TicketComment>(`/tickets/${id}/comments`, {
      body,
      is_internal: isInternal,
    });
    return data;
  },
  employee: async (userId: string): Promise<EmployeeTicketRow[]> => {
    const { data } = await apiClient.get<EmployeeTicketRow[]>(`/tickets/employee/${userId}`);
    return data;
  },
  report: async (params: { category?: string; date_from?: string; date_to?: string }): Promise<TicketReport> => {
    const { data } = await apiClient.get<TicketReport>(`/tickets/reports/summary${buildQuery(params)}`);
    return data;
  },
  reconciliation: async (): Promise<TicketReconciliation> => {
    const { data } = await apiClient.get<TicketReconciliation>('/tickets/reconciliation');
    return data;
  },
  runSla: async (): Promise<Record<string, number>> => {
    const { data } = await apiClient.post<Record<string, number>>('/tickets/sla/run');
    return data;
  },
  listRoutes: async (): Promise<TicketCategoryRoute[]> => {
    const { data } = await apiClient.get<TicketCategoryRoute[]>('/tickets/routes');
    return data;
  },
  setRoute: async (category: string, payload: TicketCategoryRouteUpdate): Promise<TicketCategoryRoute> => {
    const { data } = await apiClient.put<TicketCategoryRoute>(`/tickets/routes/${category}`, payload);
    return data;
  },
  listRules: async (): Promise<TicketRoutingRule[]> => {
    const { data } = await apiClient.get<TicketRoutingRule[]>('/tickets/routing-rules');
    return data;
  },
  createRule: async (payload: TicketRoutingRuleWrite): Promise<TicketRoutingRule> => {
    const { data } = await apiClient.post<TicketRoutingRule>('/tickets/routing-rules', payload);
    return data;
  },
  updateRule: async (id: string, payload: TicketRoutingRuleWrite): Promise<TicketRoutingRule> => {
    const { data } = await apiClient.put<TicketRoutingRule>(`/tickets/routing-rules/${id}`, payload);
    return data;
  },
  listSla: async (): Promise<TicketSlaPolicy[]> => {
    const { data } = await apiClient.get<TicketSlaPolicy[]>('/tickets/sla-policies');
    return data;
  },
  saveSla: async (payload: TicketSlaPolicy): Promise<TicketSlaPolicy> => {
    const { id: _id, ...body } = payload;
    void _id;
    const { data } = await apiClient.put<TicketSlaPolicy>('/tickets/sla-policies', body);
    return data;
  },
};
