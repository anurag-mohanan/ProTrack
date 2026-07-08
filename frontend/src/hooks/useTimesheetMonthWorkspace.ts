import { useCallback, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  bulkSaveTimesheetEntries,
  deleteTimesheetEntry,
  ensureWeekTimesheet,
  fetchTimesheetEntries,
  fetchTimesheets,
} from '../api/timesheets';
import { fetchNonProductiveCodes, fetchTaskTypes, fetchUsers } from '../api/lookups';
import { fetchHolidays } from '../api/settings';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { getProjects } from '../services/projectService';
import {
  approveTimesheet,
  rejectTimesheet,
  returnTimesheetToDraft,
  submitTimesheet,
  timesheetQueryKeys,
} from '../services/timesheetService';
import type { CurrentUser, Timesheet, TimesheetEntry } from '../types';
import { isEntryDateCalendarLocked } from '../utils/timesheetLocking';
import { isAdminRole } from '../utils/permissions';
import {
  countWorkingDays,
  monthBounds,
  summarizeDailyHoursFromEntries,
  summarizeMonthEntries,
  weekStartMonday,
} from '../utils/timesheetMonth';
import { invalidateTimesheetRelatedQueries } from '../utils/queryInvalidation';

const ACTIVE_PROJECT_STATUSES = new Set(['currently_being_worked_on', 'on_hold']);

export function useTimesheetMonthWorkspace(
  user: CurrentUser | null,
  monthValue: string,
  viewAllUsers = false,
) {
  const queryClient = useQueryClient();
  const bounds = useMemo(() => monthBounds(monthValue), [monthValue]);
  const userId = user?.id;
  const dailyLimit = user?.working_hours_per_day ?? 8;

  const holidaysQuery = useQuery({
    queryKey: ['settings', 'holidays'],
    queryFn: fetchHolidays,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const projectsQuery = useQuery({
    queryKey: ['projects', 'timesheet-workspace'],
    queryFn: () => getProjects({ lifecycle: 'active' }),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const npCodesQuery = useQuery({
    queryKey: ['non-productive-codes', 'timesheet'],
    queryFn: fetchNonProductiveCodes,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const taskTypesQuery = useQuery({
    queryKey: ['task-types', 'timesheet'],
    queryFn: () => fetchTaskTypes(),
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users', 'timesheet-overview'],
    queryFn: fetchUsers,
    enabled: viewAllUsers,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const scopeUserId = viewAllUsers ? undefined : userId;

  const timesheetsQuery = useQuery({
    queryKey: [...timesheetQueryKeys.month(monthValue, userId), viewAllUsers ? 'all' : 'self'],
    queryFn: () =>
      fetchTimesheets({
        user_id: scopeUserId,
        month: monthValue,
        limit: viewAllUsers ? 500 : 20,
      }),
    enabled: Boolean(userId),
    staleTime: QUERY_STALE_TIMES.timesheetMonth,
    gcTime: 15 * 60_000,
  });

  const entriesQuery = useQuery({
    queryKey: [
      ...timesheetQueryKeys.monthEntries(monthValue, userId),
      viewAllUsers ? 'all' : 'self',
    ],
    queryFn: () =>
      fetchTimesheetEntries({
        user_id: scopeUserId,
        entry_date_from: bounds.start,
        entry_date_to: bounds.end,
        limit: 500,
      }),
    enabled: Boolean(userId),
    staleTime: QUERY_STALE_TIMES.timesheetMonth,
    gcTime: 15 * 60_000,
  });

  const holidayDates = useMemo(
    () => new Set((holidaysQuery.data ?? []).map((holiday) => holiday.holiday_date)),
    [holidaysQuery.data],
  );

  const activeProjects = useMemo(
    () =>
      (projectsQuery.data ?? []).filter(
        (project) =>
          !project.is_archived &&
          !project.is_deleted &&
          ACTIVE_PROJECT_STATUSES.has(project.execution_status),
      ),
    [projectsQuery.data],
  );

  const entries = entriesQuery.data ?? [];
  const timesheets = timesheetsQuery.data ?? [];

  const timesheetById = useMemo(
    () => new Map(timesheets.map((sheet) => [sheet.id, sheet])),
    [timesheets],
  );

  const draftTimesheets = useMemo(
    () => timesheets.filter((sheet) => sheet.status === 'draft'),
    [timesheets],
  );

  const monthStatus = useMemo((): Timesheet['status'] | 'draft' => {
    if (!timesheets.length) return 'draft';
    if (timesheets.every((sheet) => sheet.status === 'approved')) return 'approved';
    if (timesheets.some((sheet) => sheet.status === 'submitted')) return 'submitted';
    if (timesheets.some((sheet) => sheet.status === 'rejected')) return 'rejected';
    return 'draft';
  }, [timesheets]);

  const workingDayCount = countWorkingDays(bounds.days, holidayDates);
  const expectedHours = workingDayCount * dailyLimit;
  const summary = useMemo(
    () => summarizeMonthEntries(entries, expectedHours),
    [entries, expectedHours],
  );
  const dailyTotals = useMemo(() => summarizeDailyHoursFromEntries(entries), [entries]);

  const invalidateMonth = useCallback(() => {
    invalidateTimesheetRelatedQueries(queryClient);
    void queryClient.invalidateQueries({
      queryKey: timesheetQueryKeys.month(monthValue, userId),
    });
    void queryClient.invalidateQueries({
      queryKey: timesheetQueryKeys.monthEntries(monthValue, userId),
    });
  }, [monthValue, queryClient, userId]);

  const saveEntryMutation = useMutation({
    mutationFn: async (payload: {
      entryId?: string | null;
      entryDate: string;
      toolValue: string;
      taskTypeId?: string | null;
      hours: number;
      notes?: string;
      isBillable?: boolean;
    }) => {
      if (!userId) throw new Error('Not authenticated');

      const weekStart = weekStartMonday(payload.entryDate);
      const timesheet = await ensureWeekTimesheet({
        user_id: userId,
        week_start: weekStart,
      });

      const isNp = payload.toolValue.startsWith('np:');
      const isProject = payload.toolValue.startsWith('project:');

      if (!isNp && !isProject) {
        throw new Error('Select a valid tool number or NP code.');
      }

      if (isProject) {
        const projectId = payload.toolValue.replace('project:', '');
        if (!payload.taskTypeId) {
          throw new Error('Select a task for project work.');
        }
        const result = await bulkSaveTimesheetEntries({
          upserts: [
            {
              id: payload.entryId ?? null,
              timesheet_id: timesheet.id,
              work_category: 'productive',
              project_id: projectId,
              task_type_id: payload.taskTypeId,
              entry_date: payload.entryDate,
              hours: payload.hours,
              is_billable: payload.isBillable ?? true,
              description: payload.notes?.trim() || null,
            },
          ],
          deletes: [],
        });
        return result.upserted[0];
      }

      const npCodeId = payload.toolValue.replace('np:', '');
      const result = await bulkSaveTimesheetEntries({
        upserts: [
          {
            id: payload.entryId ?? null,
            timesheet_id: timesheet.id,
            work_category: 'non_productive',
            non_productive_code_id: npCodeId,
            entry_date: payload.entryDate,
            hours: payload.hours,
            is_billable: payload.isBillable ?? false,
            description: payload.notes?.trim() || null,
          },
        ],
        deletes: [],
      });
      return result.upserted[0];
    },
    onSuccess: () => {
      invalidateMonth();
    },
  });

  const deleteEntryMutation = useMutation({
    mutationFn: deleteTimesheetEntry,
    onSuccess: () => {
      invalidateMonth();
    },
  });

  const submitMonthMutation = useMutation({
    mutationFn: async () => {
      const targets = draftTimesheets.filter((sheet) =>
        entries.some((entry) => entry.timesheet_id === sheet.id),
      );
      if (!targets.length) {
        throw new Error('No draft timesheets with entries to submit.');
      }
      await Promise.all(targets.map((sheet) => submitTimesheet(sheet.id)));
    },
    onSuccess: () => {
      invalidateMonth();
    },
  });

  const workflowMutation = useMutation({
    mutationFn: async ({
      action,
      timesheetId,
      comments,
    }: {
      action: 'approve' | 'reject' | 'return';
      timesheetId: string;
      comments?: string;
    }) => {
      if (action === 'approve') return approveTimesheet(timesheetId, comments);
      if (action === 'reject') {
        return rejectTimesheet(timesheetId, comments ?? 'Rejected from monthly workspace');
      }
      return returnTimesheetToDraft(timesheetId);
    },
    onSuccess: () => {
      invalidateMonth();
    },
  });

  const isEntryEditable = useCallback(
    (entry: TimesheetEntry) => {
      // Editability depends only on the calendar rule (current + previous two
      // months). Workflow status (submitted/approved/rejected) does not lock.
      const adminOverride = user ? isAdminRole(user.role_name ?? '') : false;
      return !isEntryDateCalendarLocked(entry.entry_date, { adminOverride });
    },
    [user],
  );

  const isLoading =
    holidaysQuery.isLoading ||
    projectsQuery.isLoading ||
    npCodesQuery.isLoading ||
    taskTypesQuery.isLoading ||
    timesheetsQuery.isLoading ||
    entriesQuery.isLoading;

  const error =
    holidaysQuery.error ??
    projectsQuery.error ??
    npCodesQuery.error ??
    taskTypesQuery.error ??
    timesheetsQuery.error ??
    entriesQuery.error;

  const lookupError =
    projectsQuery.error ?? npCodesQuery.error ?? taskTypesQuery.error ?? null;

  const refetchLookups = useCallback(() => {
    void projectsQuery.refetch();
    void npCodesQuery.refetch();
    void taskTypesQuery.refetch();
    void holidaysQuery.refetch();
  }, [holidaysQuery, npCodesQuery, projectsQuery, taskTypesQuery]);

  return {
    bounds,
    holidayDates,
    activeProjects,
    npCodes: npCodesQuery.data ?? [],
    taskTypes: taskTypesQuery.data ?? [],
    allUsers: usersQuery.data ?? [],
    entries,
    timesheets,
    timesheetById,
    draftTimesheets,
    monthStatus,
    workingDayCount,
    dailyLimit,
    summary,
    dailyTotals,
    isLoading,
    error,
    lookupError,
    refetchLookups,
    saveEntryMutation,
    deleteEntryMutation,
    submitMonthMutation,
    workflowMutation,
    isEntryEditable,
    invalidateMonth,
  };
}
