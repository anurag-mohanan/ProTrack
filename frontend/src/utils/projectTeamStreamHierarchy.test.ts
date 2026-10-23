import { describe, expect, it } from 'vitest';
import { groupProjectsByTeamThenStream } from './projectTeamStreamHierarchy';
import type { Project, Stream } from '../types';
import type { Team } from '../types/Team';

function team(id: string, name: string): Team {
  return { id, name, is_active: true, projects_enabled: true } as Team;
}

function project(id: string, teamId: string): Project {
  return {
    id,
    team_id: teamId,
    stream_id: 's1',
    execution_status: 'currently_being_worked_on',
    is_archived: false,
    is_deleted: false,
  } as Project;
}

const streams = [{ id: 's1', name: 'Design' }] as Stream[];
const teams = [team('t1', 'Alpha'), team('t2', 'Bravo'), team('t3', 'Charlie')];

describe('groupProjectsByTeamThenStream empty teams', () => {
  it('drops teams without projects unless they are requested', () => {
    const sections = groupProjectsByTeamThenStream([project('p1', 't2')], teams, streams);
    expect(sections.map((section) => section.teamId)).toEqual(['t2']);
  });

  it('keeps requested empty teams as sections with no streams, in name order', () => {
    const sections = groupProjectsByTeamThenStream([project('p1', 't2')], teams, streams, [], {
      emptyTeamIds: ['t3', 't1'],
    });
    expect(sections.map((section) => section.teamName)).toEqual(['Alpha', 'Bravo', 'Charlie']);
    const alpha = sections.find((section) => section.teamId === 't1');
    expect(alpha?.streams).toEqual([]);
    expect(alpha?.activeCount).toBe(0);
  });

  it('follows the leader team order when one is given', () => {
    const sections = groupProjectsByTeamThenStream([project('p1', 't2')], teams, streams, [], {
      leaderTeamIds: ['t3', 't2'],
      includeEmptyLeaderTeams: false,
      emptyTeamIds: ['t3'],
    });
    expect(sections.map((section) => section.teamId)).toEqual(['t3', 't2']);
  });

  it('ignores unknown team ids', () => {
    const sections = groupProjectsByTeamThenStream([], teams, streams, [], { emptyTeamIds: ['missing'] });
    expect(sections).toEqual([]);
  });
});
