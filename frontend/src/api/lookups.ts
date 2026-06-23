import type { Customer, TaskType, User } from '../types';
import { apiClient } from './client';

export async function fetchCustomers(): Promise<Customer[]> {
  const { data } = await apiClient.get<Customer[]>('/customers');
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
