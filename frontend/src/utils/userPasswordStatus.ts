import type { User } from '../types';
import { formatDateTime } from './format';

export type UserPasswordStatusColor = 'warning' | 'success' | 'default';

export interface UserPasswordStatus {
  label: string;
  color: UserPasswordStatusColor;
  detail?: string;
}

type PasswordStatusUser = Pick<
  User,
  'must_change_password' | 'password_changed_at' | 'password_changed'
>;

export function getUserPasswordStatus(user: PasswordStatusUser): UserPasswordStatus {
  if (user.must_change_password) {
    return {
      label: 'Must change password',
      color: 'warning',
      detail: 'User must set a new password on next login',
    };
  }
  if (user.password_changed_at) {
    const changedAt = formatDateTime(user.password_changed_at);
    return {
      label: 'Custom password',
      color: 'success',
      detail: changedAt ? `Changed ${changedAt}` : 'User changed their password',
    };
  }
  if (user.password_changed) {
    return { label: 'Custom password', color: 'success' };
  }
  return {
    label: 'Default password',
    color: 'default',
    detail: 'Still using the org default or admin-assigned password',
  };
}

export function formatUserPasswordAuditValue(user: PasswordStatusUser): string {
  const status = getUserPasswordStatus(user);
  if (user.must_change_password) {
    return 'Must change on next login';
  }
  if (user.password_changed_at) {
    return formatDateTime(user.password_changed_at) || status.label;
  }
  return status.label;
}
