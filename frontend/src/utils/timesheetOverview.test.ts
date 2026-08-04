import {
  buildDesignerTimesheetSections,
  buildTeamTimesheetSections,
  filterEntriesForTeamMembership,
} from './timesheetOverview';
import type { TimesheetOverviewTeam, TimesheetOverviewUser } from '../types/TimesheetEntry';
import type { TimesheetEntry } from '../types';

function entry(partial: Partial<TimesheetEntry> & Pick<TimesheetEntry, 'id' | 'user_id' | 'entry_date' | 'hours'>): TimesheetEntry {
  return {
    timesheet_id: 'ts-1',
    work_category: 'productive',
    is_billable: true,
    ...partial,
  } as TimesheetEntry;
}

describe('filterEntriesForTeamMembership', () => {
  it('does not fall back to all hours when membership windows are missing', () => {
    const rows = [
      entry({
        id: 'e1',
        user_id: 'u1',
        entry_date: '2026-07-10',
        hours: 8,
      }),
    ];
    const filtered = filterEntriesForTeamMembership(
      rows,
      new Set(['u1']),
      {},
      { requireMembershipDates: true },
    );
    expect(filtered).toEqual([]);
  });

  it('clips entries to the team membership window', () => {
    const rows = [
      entry({ id: 'e1', user_id: 'u1', entry_date: '2026-07-10', hours: 8 }),
      entry({ id: 'e2', user_id: 'u1', entry_date: '2026-07-25', hours: 6 }),
    ];
    const filtered = filterEntriesForTeamMembership(
      rows,
      new Set(['u1']),
      { u1: [{ start: '2026-07-20', end: '2026-07-31' }] },
      { requireMembershipDates: true },
    );
    expect(filtered.map((row) => row.id)).toEqual(['e2']);
  });
});

describe('buildTeamTimesheetSections', () => {
  it('does not duplicate the same hours across multiple teams', () => {
    const users: TimesheetOverviewUser[] = [
      {
        id: 'u1',
        first_name: 'Ranjith',
        last_name: 'K',
        email: 'r@example.com',
        team_ids: ['t1', 't2'],
        working_hours_per_day: 8,
        requires_timesheet: true,
      },
    ];
    const teams: TimesheetOverviewTeam[] = [
      {
        team_id: 't1',
        team_name: 'Team One',
        user_ids: ['u1'],
        membership_windows: { u1: [{ start: '2026-07-01', end: '2026-07-19' }] },
      },
      {
        team_id: 't2',
        team_name: 'Team Two',
        user_ids: ['u1'],
        membership_windows: { u1: [{ start: '2026-07-20', end: '2026-07-31' }] },
      },
    ];
    const entries = [
      entry({ id: 'e1', user_id: 'u1', entry_date: '2026-07-10', hours: 8 }),
      entry({ id: 'e2', user_id: 'u1', entry_date: '2026-07-25', hours: 6 }),
    ];

    const sections = buildTeamTimesheetSections(teams, users, entries, 22);
    expect(sections).toHaveLength(2);
    expect(sections[0].summary.enteredHours).toBe(8);
    expect(sections[1].summary.enteredHours).toBe(6);
    expect(sections[0].entriesByUserId.get('u1')?.map((row) => row.id)).toEqual(['e1']);
    expect(sections[1].entriesByUserId.get('u1')?.map((row) => row.id)).toEqual(['e2']);
  });

  it('keeps management section hours unsplit when windows are empty', () => {
    const users: TimesheetOverviewUser[] = [
      {
        id: 'u1',
        first_name: 'Leader',
        last_name: 'One',
        email: 'l@example.com',
        team_ids: ['corp'],
        working_hours_per_day: 8,
        requires_timesheet: true,
      },
    ];
    const teams: TimesheetOverviewTeam[] = [
      {
        team_id: null,
        team_name: 'Management / Leadership',
        user_ids: ['u1'],
        membership_windows: {},
        section_kind: 'management',
      },
    ];
    const entries = [entry({ id: 'e1', user_id: 'u1', entry_date: '2026-07-10', hours: 8 })];
    const sections = buildTeamTimesheetSections(teams, users, entries, 22);
    expect(sections).toHaveLength(1);
    expect(sections[0].sectionKind).toBe('management');
    expect(sections[0].summary.enteredHours).toBe(8);
  });
});

describe('buildDesignerTimesheetSections', () => {
  it('puts management users in a separate full-hours section', () => {
    const users: TimesheetOverviewUser[] = [
      {
        id: 'leader',
        first_name: 'Ranjith',
        last_name: 'Lead',
        email: 'lead@example.com',
        team_ids: ['corp'],
        working_hours_per_day: 8,
        requires_timesheet: true,
      },
      {
        id: 'designer',
        first_name: 'Ada',
        last_name: 'Designer',
        email: 'ada@example.com',
        team_ids: ['t1'],
        working_hours_per_day: 8,
        requires_timesheet: true,
      },
    ];
    const teams: TimesheetOverviewTeam[] = [
      {
        team_id: null,
        team_name: 'Management / Leadership',
        user_ids: ['leader'],
        membership_windows: {},
        section_kind: 'management',
      },
    ];
    const entries = [
      entry({ id: 'e1', user_id: 'leader', entry_date: '2026-07-10', hours: 7 }),
      entry({ id: 'e2', user_id: 'designer', entry_date: '2026-07-10', hours: 8 }),
    ];
    const sections = buildDesignerTimesheetSections(users, entries, 22, teams);
    expect(sections.map((section) => section.teamName)).toEqual([
      'Management / Leadership',
      'All designers',
    ]);
    expect(sections[0].summary.enteredHours).toBe(7);
    expect(sections[1].summary.enteredHours).toBe(8);
  });
});
