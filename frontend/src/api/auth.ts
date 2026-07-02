import { apiClient } from './client';
import type { ChangePasswordRequest, CurrentUser, LoginRequest, TokenResponse } from '../types';

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', credentials);
  return data;
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const { data } = await apiClient.get<CurrentUser>('/auth/me', { timeout: 15_000 });
  return data;
}

export async function changePassword(payload: ChangePasswordRequest): Promise<void> {
  await apiClient.post('/auth/change-password', payload);
}

export async function logoutSession(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function impersonateUser(userId: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>(`/auth/impersonate/${userId}`);
  return data;
}

export async function stopImpersonation(): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/stop-impersonation');
  return data;
}
