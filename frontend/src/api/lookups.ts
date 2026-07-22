import type { Contact, Customer, NonProductiveCode, Stream, TaskType, User, WorkingModel } from '../types';
import { ensureArray } from '../types/pagination';
import { apiClient, buildQuery, type ListParams } from './client';

export interface ContactListParams extends ListParams {
  customer_id?: string;
}

export async function fetchCustomers(): Promise<Customer[]> {
  const { data } = await apiClient.get<unknown>('/lookups/customers');
  return ensureArray<Customer>(data);
}

export async function fetchContacts(params?: ContactListParams): Promise<Contact[]> {
  const { data } = await apiClient.get<unknown>(`/lookups/contacts${buildQuery(params)}`);
  return ensureArray<Contact>(data);
}

export async function fetchStreams(): Promise<Stream[]> {
  const { data } = await apiClient.get<unknown>('/lookups/streams');
  return ensureArray<Stream>(data);
}

export async function fetchUsers(): Promise<User[]> {
  const { data } = await apiClient.get<unknown>('/lookups/users');
  return ensureArray<User>(data);
}

export async function fetchTaskTypes(streamId?: string): Promise<TaskType[]> {
  const { data } = await apiClient.get<unknown>(
    `/lookups/task-types${buildQuery(streamId ? { stream_id: streamId } : undefined)}`,
  );
  return ensureArray<TaskType>(data);
}

export async function fetchNonProductiveCodes(): Promise<NonProductiveCode[]> {
  const { data } = await apiClient.get<unknown>('/lookups/non-productive-codes');
  return ensureArray<NonProductiveCode>(data);
}

export async function fetchOperationalRoles() {
  const { data } = await apiClient.get<unknown>('/lookups/operational-roles');
  return ensureArray<{
    id: string;
    code: string;
    name: string;
    dashboard_profile: string;
  }>(data);
}

export async function fetchTeams() {
  const { data } = await apiClient.get<unknown>('/lookups/teams');
  return ensureArray<import('../types/Team').Team>(data);
}

export async function fetchRoles(): Promise<import('../types').Role[]> {
  const { data } = await apiClient.get<unknown>('/lookups/roles');
  return ensureArray<import('../types').Role>(data);
}

export async function fetchOrgDepartments(): Promise<import('../types').OrgDepartment[]> {
  const { data } = await apiClient.get<unknown>('/lookups/org-departments');
  return ensureArray<import('../types').OrgDepartment>(data);
}

export async function fetchWorkingModels(): Promise<WorkingModel[]> {
  const { data } = await apiClient.get<unknown>('/lookups/working-models');
  return ensureArray<WorkingModel>(data);
}

export async function fetchTimesheetProjects(params?: {
  q?: string;
  limit?: number;
}): Promise<import('../types/TimesheetEntry').TimesheetProjectLookup[]> {
  const { data } = await apiClient.get<unknown>(
    `/lookups/timesheet-projects${buildQuery(params)}`,
  );
  return ensureArray<import('../types/TimesheetEntry').TimesheetProjectLookup>(data);
}

export async function fetchTimesheetProjectContext(
  projectId: string,
): Promise<import('../types/TimesheetEntry').TimesheetProjectContext> {
  const { data } = await apiClient.get<import('../types/TimesheetEntry').TimesheetProjectContext>(
    `/lookups/timesheet-projects/${projectId}/context`,
  );
  return data;
}
