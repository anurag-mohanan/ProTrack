import { useMemo } from 'react';
import {
  Checkbox,
  FormControl,
  InputLabel,
  ListItemText,
  MenuItem,
  OutlinedInput,
  Select,
  type SelectChangeEvent,
} from '@mui/material';

export interface TeamScopeOption {
  id: string;
  name: string;
}

interface TeamScopeFilterProps {
  label?: string;
  teams: TeamScopeOption[];
  selectedTeamIds: string[];
  onChange: (teamIds: string[]) => void;
  disabled?: boolean;
}

export function TeamScopeFilter({
  label = 'Teams',
  teams,
  selectedTeamIds,
  onChange,
  disabled = false,
}: TeamScopeFilterProps) {
  const allSelected = teams.length > 0 && selectedTeamIds.length === teams.length;
  const displayValue = useMemo(() => {
    if (allSelected || selectedTeamIds.length === 0) {
      return 'All My Teams';
    }
    if (selectedTeamIds.length === 1) {
      return teams.find((team) => team.id === selectedTeamIds[0])?.name ?? '1 team';
    }
    return `${selectedTeamIds.length} teams`;
  }, [allSelected, selectedTeamIds, teams]);

  const handleChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    const next = typeof value === 'string' ? value.split(',') : value;
    if (next.includes('__all__')) {
      onChange(teams.map((team) => team.id));
      return;
    }
    onChange(next);
  };

  return (
    <FormControl size="small" sx={{ minWidth: 220 }} disabled={disabled}>
      <InputLabel id="team-scope-filter-label">{label}</InputLabel>
      <Select
        labelId="team-scope-filter-label"
        multiple
        value={selectedTeamIds}
        onChange={handleChange}
        input={<OutlinedInput label={label} />}
        renderValue={() => displayValue}
      >
        <MenuItem value="__all__">
          <Checkbox checked={allSelected} />
          <ListItemText primary="All My Teams" />
        </MenuItem>
        {teams.map((team) => (
          <MenuItem key={team.id} value={team.id}>
            <Checkbox checked={selectedTeamIds.includes(team.id)} />
            <ListItemText primary={team.name} />
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
