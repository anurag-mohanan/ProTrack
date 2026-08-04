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
  /** management | delivery | unassigned | designer */
  sectionKind?: string;
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
    // Named teams: missing windows means this day does not belong here.
    // Never fall back to "all hours" — that duplicates the same person under
    // every team they have a secondary membership on.
    if (!windows?.length) return !requireMembershipDates;
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
      // Management / unassigned: full period hours. Delivery teams: membership dates.
      const clipToMembership =
        team.section_kind === 'delivery' ||
        (team.section_kind == null && team.team_id != null);
      const teamEntries = filterEntriesForTeamMembership(
        entries,
        userIdSet,
        team.membership_windows,
        { requireMembershipDates: clipToMembership },
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
        sectionKind: team.section_kind ?? (team.team_id != null ? 'delivery' : 'unassigned'),
      };
    })
    .filter((section) => section.users.length > 0);
}

function sectionFromUsers(
  teamName: string,
  users: TimesheetOverviewUser[],
  entries: TimesheetEntry[],
  workingDayCount: number,
  sectionKind: string,
  teamId: string | null = null,
): TimesheetTeamSection {
  const userIdSet = new Set(users.map((user) => user.id));
  const scopedEntries = filterEntriesForUsers(entries, userIdSet);
  const entriesByUserId = new Map<string, TimesheetEntry[]>();
  for (const entry of scopedEntries) {
    const key = entry.user_id ?? 'unknown';
    const list = entriesByUserId.get(key);
    if (list) list.push(entry);
    else entriesByUserId.set(key, [entry]);
  }
  return {
    teamId,
    teamName,
    users,
    summary: summarizeMonthEntries(scopedEntries, expectedHoursForUsers(users, workingDayCount)),
    entriesByUserId,
    sectionKind,
  };
}

/**
 * Full period hours per person (no membership clipping). Leaders from the
 * Management overview section stay in their own block so multi-team managers
 * are not mixed into the delivery designer list.
 */
export function buildDesignerTimesheetSections(
  users: TimesheetOverviewUser[],
  entries: TimesheetEntry[],
  workingDayCount: number,
  teams?: TimesheetOverviewTeam[],
): TimesheetTeamSection[] {
  const trackedUsers = [...users]
    .filter((user) => user.requires_timesheet !== false)
    .sort((left, right) => {
      const leftName = `${left.last_name} ${left.first_name}`.toLowerCase();
      const rightName = `${right.last_name} ${right.first_name}`.toLowerCase();
      return leftName.localeCompare(rightName);
    });

  const managementTeam = teams?.find((team) => team.section_kind === 'management');
  const managementIds = new Set(managementTeam?.user_ids ?? []);
  const sections: TimesheetTeamSection[] = [];

  if (managementIds.size > 0) {
    const managementUsers = trackedUsers.filter((user) => managementIds.has(user.id));
    if (managementUsers.length > 0) {
      sections.push(
        sectionFromUsers(
          managementTeam?.team_name ?? 'Management / Leadership',
          managementUsers,
          entries,
          workingDayCount,
          'management',
        ),
      );
    }
  }

  const deliveryUsers = trackedUsers.filter((user) => !managementIds.has(user.id));
  if (deliveryUsers.length > 0) {
    sections.push(
      sectionFromUsers('All designers', deliveryUsers, entries, workingDayCount, 'designer'),
    );
  }

  return sections;
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
