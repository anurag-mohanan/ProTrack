import type { TimesheetEntry } from '../types';
import type {
  MembershipDateWindow,
  TimesheetOverviewTeam,
  TimesheetOverviewUser,
} from '../types/TimesheetEntry';
import {
  summarizeMonthEntries,
  sumEntryHours,
  type TimesheetEntryLike,
  type TimesheetMonthSummary,
  weekWorkingDayCount,
} from './timesheetMonth';

export interface TimesheetTeamSection {
  teamId: string | null;
  teamName: string;
  users: TimesheetOverviewUser[];
  summary: TimesheetMonthSummary;
  /** Entries clipped to each user's membership windows on this team. */
  entriesByUserId: Map<string, TimesheetEntry[]>;
}

export function expectedHoursForUsers(
  users: Array<{ working_hours_per_day?: number }>,
  workingDayCount: number,
): number {
  return users.reduce(
    (total, user) => total + workingDayCount * (user.working_hours_per_day ?? 8),
    0,
  );
}

export function entryDateInWindows(
  entryDate: string,
  windows: MembershipDateWindow[] | undefined,
): boolean {
  if (!windows?.length) return false;
  const day = entryDate.slice(0, 10);
  return windows.some((window) => {
    const start = window.start.slice(0, 10);
    const end = window.end.slice(0, 10);
    return day >= start && day <= end;
  });
}

export function filterEntriesForUsers(
  entries: TimesheetEntry[],
  userIds: Set<string>,
): TimesheetEntry[] {
  return entries.filter((entry) => entry.user_id != null && userIds.has(entry.user_id));
}

export function filterEntriesForTeamMembership(
  entries: TimesheetEntry[],
  userIds: Set<string>,
  membershipWindows: Record<string, MembershipDateWindow[]> | undefined,
  options?: { requireMembershipDates?: boolean },
): TimesheetEntry[] {
  const requireMembershipDates = Boolean(options?.requireMembershipDates);
  // Unassigned sections have no windows and intentionally include all user entries.
  if (!requireMembershipDates) {
    if (!membershipWindows || Object.keys(membershipWindows).length === 0) {
      return filterEntriesForUsers(entries, userIds);
    }
  }
  return entries.filter((entry) => {
    if (entry.user_id == null || !userIds.has(entry.user_id)) return false;
    const windows = membershipWindows?.[entry.user_id];
    // Rostered on the team but windows missing — never hide their hours.
    if (!windows?.length) return true;
    return entryDateInWindows(entry.entry_date, windows);
  });
}

export function buildTeamTimesheetSections(
  teams: TimesheetOverviewTeam[],
  users: TimesheetOverviewUser[],
  entries: TimesheetEntry[],
  workingDayCount: number,
): TimesheetTeamSection[] {
  // Only people who must fill timesheets belong in team monitoring sections.
  const trackedUsers = users.filter((user) => user.requires_timesheet !== false);
  const usersById = new Map(trackedUsers.map((user) => [user.id, user]));

  return teams
    .map((team) => {
      const teamUsers = team.user_ids
        .map((userId) => usersById.get(userId))
        .filter((user): user is TimesheetOverviewUser => user != null)
        .filter((user) => user.requires_timesheet !== false);
      const userIdSet = new Set(teamUsers.map((user) => user.id));
      // Named teams must clip to membership start — never fall back to full history.
      const teamEntries = filterEntriesForTeamMembership(
        entries,
        userIdSet,
        team.membership_windows,
        { requireMembershipDates: team.team_id != null },
      );
      const entriesByUserId = new Map<string, TimesheetEntry[]>();
      for (const entry of teamEntries) {
        const key = entry.user_id ?? 'unknown';
        const list = entriesByUserId.get(key);
        if (list) list.push(entry);
        else entriesByUserId.set(key, [entry]);
      }
      const expectedHours = expectedHoursForUsers(teamUsers, workingDayCount);

      return {
        teamId: team.team_id,
        teamName: team.team_name,
        users: teamUsers,
        summary: summarizeMonthEntries(teamEntries, expectedHours),
        entriesByUserId,
      };
    })
    .filter((section) => section.users.length > 0);
}

export function buildScopedOverviewSummary(
  users: TimesheetOverviewUser[],
  entries: TimesheetEntryLike[],
  workingDayCount: number,
): TimesheetMonthSummary {
  const expectedHours = expectedHoursForUsers(users, workingDayCount);
  const scopedIds = new Set(users.map((user) => user.id));
  const scopedEntries = entries.filter((entry) => {
    const userId = 'user_id' in entry ? entry.user_id : null;
    return userId != null && scopedIds.has(String(userId));
  });
  return summarizeMonthEntries(scopedEntries, expectedHours);
}

export function buildWeeklyScopedSummary(
  users: TimesheetOverviewUser[],
  entries: TimesheetEntry[],
  weekStart: string,
  weekEnd: string,
  holidayDates: Set<string>,
  anchorDate: string,
): { weeklyHours: number; weeklyExpected: number } {
  const weeklyHours = sumEntryHours(
    entries.filter((entry) => entry.entry_date >= weekStart && entry.entry_date <= weekEnd),
  );
  const workingDays = weekWorkingDayCount(anchorDate, holidayDates);
  const weeklyExpected = expectedHoursForUsers(users, workingDays);
  return { weeklyHours, weeklyExpected };
}

export function buildTodayScopedSummary(
  users: TimesheetOverviewUser[],
  entries: TimesheetEntry[],
  todayIso: string,
  holidayDates: Set<string>,
): { todayHours: number; todayExpected: number } {
  const todayHours = sumEntryHours(entries.filter((entry) => entry.entry_date === todayIso));
  const isWorkingDay =
    !holidayDates.has(todayIso) &&
    new Date(`${todayIso}T12:00:00`).getDay() !== 0 &&
    new Date(`${todayIso}T12:00:00`).getDay() !== 6;
  const todayExpected = isWorkingDay
    ? expectedHoursForUsers(users, 1)
    : 0;
  return { todayHours, todayExpected };
}

export function teamSectionBreakdownLabel(summary: TimesheetMonthSummary): string {
  return `${summary.enteredHours.toFixed(1)}h entered · ${summary.billableHours.toFixed(1)} billable · ${summary.nonProductiveHours.toFixed(1)} NP · ${summary.leaveDays} leave days`;
}
