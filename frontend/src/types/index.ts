export * from './common';
export * from './Project';
export * from './Milestone';
export * from './Timesheet';
export * from './TimesheetEntry';
export * from './Dashboard';
export * from './Auth';

export interface Customer {
  id: string;
  name: string;
  code: string | null;
  is_active: boolean;
}

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role_id: string;
  is_active: boolean;
}

export interface TaskType {
  id: string;
  stream_id: string;
  name: string;
  description: string | null;
  is_billable: boolean;
  is_active: boolean;
}
