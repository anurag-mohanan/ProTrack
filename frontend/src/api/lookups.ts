import type { Contact, Customer, Stream, TaskType, User } from '../types';
import { apiClient, buildQuery, type ListParams } from './client';

export interface ContactListParams extends ListParams {
  customer_id?: string;
}

export async function fetchCustomers(): Promise<Customer[]> {
  const { data } = await apiClient.get<Customer[]>('/customers');
  return data;
}

export async function fetchContacts(params?: ContactListParams): Promise<Contact[]> {
  const { data } = await apiClient.get<Contact[]>(`/contacts${buildQuery(params)}`);
  return data;
}

export async function fetchStreams(): Promise<Stream[]> {
  const { data } = await apiClient.get<Stream[]>('/streams');
  return data;
}

export async function fetchUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>('/users');
  return data;
}

export async function fetchTaskTypes(): Promise<TaskType[]> {
  const { data } = await apiClient.get<TaskType[]>('/task-types');
  return data;
}
