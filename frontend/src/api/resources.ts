import { createResourceApi } from './client';
import type {
  Contact,
  Customer,
  Milestone,
  Project,
  ProjectMember,
  Role,
  Stream,
  TaskType,
  Timesheet,
  TimesheetEntry,
  User,
} from '../types';

export const rolesApi = createResourceApi<Role>('roles');
export const usersApi = createResourceApi<User>('users');
export const streamsApi = createResourceApi<Stream>('streams');
export const customersApi = createResourceApi<Customer>('customers');
export const contactsApi = createResourceApi<Contact>('contacts');
export const taskTypesApi = createResourceApi<TaskType>('task-types');
export const projectsApi = createResourceApi<Project>('projects');
export const projectMembersApi = createResourceApi<ProjectMember>('project-members');
export const milestonesApi = createResourceApi<Milestone>('milestones');
export const timesheetsApi = createResourceApi<Timesheet>('timesheets');
export const timesheetEntriesApi = createResourceApi<TimesheetEntry>('timesheet-entries');
