import {
  Box,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Radio,
  Select,
  Stack,
  Typography,
} from '@mui/material';

export type TeamRelationshipType =
  | 'member'
  | 'team_leader'
  | 'engineering_manager'
  | 'reviewer';

export interface UserTeamAssignmentFormValue {
  team_id: string;
  team_name: string;
  relationship_type: TeamRelationshipType;
  is_primary: boolean;
}

interface UserTeamAssignmentsProps {
  teams: Array<{ id: string; name: string }>;
  value: UserTeamAssignmentFormValue[];
  onChange: (next: UserTeamAssignmentFormValue[]) => void;
  disabled?: boolean;
}

const RELATIONSHIP_OPTIONS: Array<{ value: TeamRelationshipType; label: string }> = [
  { value: 'member', label: 'Member' },
  { value: 'team_leader', label: 'Team Leader' },
  { value: 'engineering_manager', label: 'Engineering Manager' },
  { value: 'reviewer', label: 'Reviewer' },
];

export function UserTeamAssignments({
  teams,
  value,
  onChange,
  disabled = false,
}: UserTeamAssignmentsProps) {
  const selectedIds = new Set(value.map((row) => row.team_id));

  const toggleTeam = (teamId: string, teamName: string, checked: boolean) => {
    if (checked) {
      const next = [
        ...value,
        {
          team_id: teamId,
          team_name: teamName,
          relationship_type: 'member' as TeamRelationshipType,
          is_primary: value.length === 0,
        },
      ];
      onChange(next);
      return;
    }
    const remaining = value.filter((row) => row.team_id !== teamId);
    if (remaining.length > 0 && !remaining.some((row) => row.is_primary)) {
      remaining[0] = { ...remaining[0], is_primary: true };
    }
    onChange(remaining);
  };

  const updateRow = (
    teamId: string,
    patch: Partial<Pick<UserTeamAssignmentFormValue, 'relationship_type' | 'is_primary'>>,
  ) => {
    onChange(
      value.map((row) => {
        if (row.team_id !== teamId) {
          if (patch.is_primary) {
            return { ...row, is_primary: false };
          }
          return row;
        }
        return { ...row, ...patch };
      }),
    );
  };

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Teams
      </Typography>
      <Stack spacing={1}>
        {teams.map((team) => {
          const assignment = value.find((row) => row.team_id === team.id);
          const checked = selectedIds.has(team.id);
          return (
            <Box
              key={team.id}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 1.25,
              }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={checked}
                    disabled={disabled}
                    onChange={(event) =>
                      toggleTeam(team.id, team.name, event.target.checked)
                    }
                  />
                }
                label={team.name}
              />
              {checked && assignment ? (
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 1, pl: 4 }}>
                  <FormControl size="small" sx={{ minWidth: 180 }}>
                    <InputLabel id={`relationship-${team.id}`}>Relationship</InputLabel>
                    <Select
                      labelId={`relationship-${team.id}`}
                      label="Relationship"
                      value={assignment.relationship_type}
                      disabled={disabled}
                      onChange={(event) =>
                        updateRow(team.id, {
                          relationship_type: event.target.value as TeamRelationshipType,
                        })
                      }
                    >
                      {RELATIONSHIP_OPTIONS.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControlLabel
                    control={
                      <Radio
                        checked={assignment.is_primary}
                        disabled={disabled}
                        onChange={() => updateRow(team.id, { is_primary: true })}
                      />
                    }
                    label="Primary team"
                  />
                </Stack>
              ) : null}
            </Box>
          );
        })}
      </Stack>
    </Box>
  );
}
