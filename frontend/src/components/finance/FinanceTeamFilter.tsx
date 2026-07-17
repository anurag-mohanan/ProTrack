import { MenuItem, Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchTeams } from '../../api/lookups';
import { FilterSelect } from '../ui/design-system/FilterSelect';

const STORAGE_KEY = 'finance.selectedTeamId';

export function readStoredFinanceTeamId(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

export function writeStoredFinanceTeamId(teamId: string) {
  try {
    if (!teamId) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, teamId);
  } catch {
    /* ignore */
  }
}

export function teamQueryParam(teamId: string): string {
  return teamId ? `?team_id=${encodeURIComponent(teamId)}` : '';
}

interface FinanceTeamFilterProps {
  value: string;
  onChange: (teamId: string) => void;
}

export function FinanceTeamFilter({ value, onChange }: FinanceTeamFilterProps) {
  const teamsQuery = useQuery({
    queryKey: ['lookup-teams'],
    queryFn: fetchTeams,
  });
  const teams = teamsQuery.data ?? [];

  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={1.5}
      sx={{ mb: 2, alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
    >
      <Typography variant="body2" color="text.secondary">
        Team lens: costs, salaries, renewals, and commercial terms are scoped to the selected team
        (shared HQ costs use Corporate / Management).
      </Typography>
      <FilterSelect
        label="Team"
        value={value}
        fullWidth={false}
        sx={{ minWidth: 260 }}
        onChange={(event) => {
          const next = String(event.target.value);
          writeStoredFinanceTeamId(next);
          onChange(next);
        }}
      >
        <MenuItem value="">All teams</MenuItem>
        {teams.map((team) => (
          <MenuItem key={team.id} value={team.id}>
            {team.name}
          </MenuItem>
        ))}
      </FilterSelect>
    </Stack>
  );
}
