import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
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
  /** When false, person is omitted from timesheet reports for this team. */
  include_in_timesheet_reports: boolean;
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
      onChange([
        ...value,
        {
          team_id: teamId,
          team_name: teamName,
          relationship_type: 'member',
          is_primary: false,
          include_in_timesheet_reports: true,
        },
      ]);
      return;
    }
    onChange(value.filter((row) => row.team_id !== teamId));
  };

  const updateRow = (
    teamId: string,
    patch: Partial<
      Pick<
        UserTeamAssignmentFormValue,
        'relationship_type' | 'is_primary' | 'include_in_timesheet_reports'
      >
    >,
  ) => {
    onChange(
      value.map((row) => {
        if (row.team_id !== teamId) {
          // Only one primary at a time when setting primary true
          if (patch.is_primary === true) {
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
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        Teams
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Select one or more teams. Primary team is optional — useful for Engineering Managers and
        Design Leaders who oversee multiple teams without a single home team. Uncheck “Include in
        timesheet reports” to hide a person from that team’s timesheet / engineering exports.
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
                    <InputLabel id={`relationship-${team.id}`} shrink>
                      Relationship
                    </InputLabel>
                    <Select
                      labelId={`relationship-${team.id}`}
                      label="Relationship"
                      notched
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
                      <Checkbox
                        checked={assignment.is_primary}
                        disabled={disabled}
                        onChange={(event) =>
                          updateRow(team.id, { is_primary: event.target.checked })
                        }
                      />
                    }
                    label="Primary (optional)"
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={assignment.include_in_timesheet_reports}
                        disabled={disabled}
                        onChange={(event) =>
                          updateRow(team.id, {
                            include_in_timesheet_reports: event.target.checked,
                          })
                        }
                      />
                    }
                    label="Include in timesheet reports"
                  />
                </Stack>
              ) : null}
            </Box>
          );
        })}
      </Stack>
      {value.length > 0 && !value.some((row) => row.is_primary) ? (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          No primary team selected — allowed for multi-team leaders.
        </Typography>
      ) : null}
      {value.some((row) => row.is_primary) ? (
        <Box sx={{ mt: 1 }}>
          <Button
            size="small"
            disabled={disabled}
            onClick={() =>
              onChange(value.map((row) => ({ ...row, is_primary: false })))
            }
          >
            Clear primary team
          </Button>
        </Box>
      ) : null}
    </Box>
  );
}
