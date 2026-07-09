import { apiClient, buildQuery, type ListParams } from './client';
import {
  isPaginatedResponse,
  normalizePaginatedResponse,
  unwrapListResponse,
  type PaginatedResponse,
} from '../types/pagination';
import type {
  Contact,
  Customer,
  Role,
  Stream,
  TaskType,
  User,
} from '../types';

export function createResourceApi<
  T,
  TCreate = Partial<T>,
  TUpdate = Partial<T>,
>(resource: string) {
  return {
    list: async (params?: ListParams): Promise<T[]> => {
      const { data } = await apiClient.get<T[] | PaginatedResponse<T>>(
        `/${resource}${buildQuery(params)}`,
      );
      return unwrapListResponse(data);
    },
    listPaginated: async (params?: ListParams): Promise<PaginatedResponse<T>> => {
      const { data } = await apiClient.get<T[] | PaginatedResponse<T>>(
        `/${resource}${buildQuery(params)}`,
      );
      return normalizePaginatedResponse(data);
    },
    get: async (id: string): Promise<T> => {
      const { data } = await apiClient.get<T>(`/${resource}/${id}`);
      return data;
    },
    create: async (payload: TCreate): Promise<T> => {
      const { data } = await apiClient.post<T>(`/${resource}`, payload);
      return data;
    },
    update: async (id: string, payload: TUpdate): Promise<T> => {
      const { data } = await apiClient.patch<T>(`/${resource}/${id}`, payload);
      return data;
    },
    remove: async (id: string): Promise<void> => {
      await apiClient.delete(`/${resource}/${id}`);
    },
  };
}

export const rolesApi = createResourceApi<Role>('roles');
export const usersApi = createResourceApi<User>('users');
export const streamsApi = createResourceApi<Stream>('streams');
export const teamsApi = createResourceApi<
  import('../types/Team').Team,
  import('../types/Team').TeamCreate,
  import('../types/Team').TeamUpdate
>('teams');
export const customersApi = createResourceApi<Customer>('customers');
export const contactsApi = createResourceApi<Contact>('contacts');
export const taskTypesApi = createResourceApi<TaskType>('task-types');
export const nonProductiveCodesApi = createResourceApi<
  import('../types').NonProductiveCode,
  import('../types').NonProductiveCodeCreate,
  import('../types').NonProductiveCodeUpdate
>('non-productive-codes');

export interface ResetPasswordPayload {
  password?: string;
  generate_temporary?: boolean;
}

export interface ResetPasswordResponse {
  temporary_password: string | null;
  message: string;
}

export async function resetUserPassword(
  userId: string,
  payload: ResetPasswordPayload,
): Promise<ResetPasswordResponse> {
  const { data } = await apiClient.post<ResetPasswordResponse>(
    `/users/${userId}/reset-password`,
    payload,
  );
  return data;
}

export async function forceUserPasswordChange(userId: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/force-password-change`);
  return data;
}

export async function unlockUser(userId: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/unlock`);
  return data;
}

export async function setUserTemporaryPassword(
  userId: string,
): Promise<ResetPasswordResponse> {
  const { data } = await apiClient.post<ResetPasswordResponse>(
    `/users/${userId}/set-temporary-password`,
  );
  return data;
}

export async function setUserMustChangePassword(
  userId: string,
  required: boolean,
): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/must-change-password`, {
    required,
  });
  return data;
}

export async function archiveUser(userId: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/archive`);
  return data;
}

export async function softDeleteUser(userId: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${userId}/soft-delete`);
  return data;
}

export async function fetchUserProfileDetail(userId: string): Promise<import('./preferences').UserProfile> {
  const { data } = await apiClient.get<import('./preferences').UserProfile>(
    `/users/${userId}/profile`,
  );
  return data;
}
