import { Autocomplete, Box, TextField } from '@mui/material';
import type { Customer, Team, User } from '../../types';
import type { ExecutionStatus, ProjectStage } from '../../types/common';
import type { ProjectType } from '../../types/ProjectTemplate';
import { FormSelect } from '../ui/design-system';
import {
  EXECUTION_STATUS_LABELS,
  PROJECT_STAGE_LABELS,
} from '../../types/common';
import { userDisplayName } from '../../utils/format';

export interface ProjectFilterValues {
  customerIds: string[];
  projectTypeId: string;
  teamIds: string[];
  projectStage: ProjectStage | 'all';
  executionStatus: ExecutionStatus | 'all';
  designLeaderId: string;
  designerId: string;
  surfacerId: string;
}

interface ProjectFiltersBarProps {
  customers: Customer[];
  teams: Team[];
  projectTypes: ProjectType[];
  users: User[];
  values: ProjectFilterValues;
  onChange: (values: ProjectFilterValues) => void;
}

const allOption = { value: 'all', label: 'All' };

export function ProjectFiltersBar({
  customers,
  teams,
  projectTypes,
  users,
  values,
  onChange,
}: ProjectFiltersBarProps) {
  const selectedCustomers = customers.filter((customer) =>
    values.customerIds.includes(customer.id),
  );
  const selectedTeams = teams.filter((team) => values.teamIds.includes(team.id));

  const userOptions = users.map((user) => ({
    value: user.id,
    label: userDisplayName(user),
  }));

  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', width: '100%' }}>
      <Autocomplete
        multiple
        options={customers}
        value={selectedCustomers}
        getOptionLabel={(option) => option.name}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        onChange={(_, next) =>
          onChange({
            ...values,
            customerIds: next.map((customer) => customer.id),
          })
        }
        renderInput={(params) => (
          <TextField {...params} label="Customers" placeholder="All Customers" />
        )}
        sx={{ minWidth: 260, flex: 1 }}
      />

      <FormSelect
        label="Project Type"
        value={values.projectTypeId}
        options={[allOption, ...projectTypes.map((type) => ({ value: type.id, label: type.name }))]}
        onChange={(event) =>
          onChange({ ...values, projectTypeId: String(event.target.value) })
        }
        sx={{ minWidth: 180 }}
      />

      <Autocomplete
        multiple
        options={teams}
        value={selectedTeams}
        getOptionLabel={(option) => option.name}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        onChange={(_, next) =>
          onChange({
            ...values,
            teamIds: next.map((team) => team.id),
          })
        }
        renderInput={(params) => (
          <TextField {...params} label="Teams" placeholder="All Teams" />
        )}
        sx={{ minWidth: 220, flex: 1 }}
      />

      <FormSelect
        label="Project Stage"
        value={values.projectStage}
        options={[
          { value: 'all', label: 'All Stages' },
          ...(
            Object.entries(PROJECT_STAGE_LABELS) as Array<[ProjectStage, string]>
          ).map(([value, label]) => ({ value, label })),
        ]}
        onChange={(event) =>
          onChange({
            ...values,
            projectStage: event.target.value as ProjectStage | 'all',
          })
        }
        sx={{ minWidth: 180 }}
      />

      <FormSelect
        label="Execution Status"
        value={values.executionStatus}
        options={[
          { value: 'all', label: 'All Execution Statuses' },
          ...(
            Object.entries(EXECUTION_STATUS_LABELS) as Array<[ExecutionStatus, string]>
          ).map(([value, label]) => ({ value, label })),
        ]}
        onChange={(event) =>
          onChange({
            ...values,
            executionStatus: event.target.value as ExecutionStatus | 'all',
          })
        }
        sx={{ minWidth: 220 }}
      />

      <FormSelect
        label="Design Leader"
        searchable
        value={values.designLeaderId}
        options={[allOption, ...userOptions]}
        onChange={(event) =>
          onChange({ ...values, designLeaderId: String(event.target.value) })
        }
        sx={{ minWidth: 200 }}
      />

      <FormSelect
        label="Designer"
        searchable
        value={values.designerId}
        options={[allOption, ...userOptions]}
        onChange={(event) =>
          onChange({ ...values, designerId: String(event.target.value) })
        }
        sx={{ minWidth: 180 }}
      />

      <FormSelect
        label="Surfacer"
        searchable
        value={values.surfacerId}
        options={[allOption, ...userOptions]}
        onChange={(event) =>
          onChange({ ...values, surfacerId: String(event.target.value) })
        }
        sx={{ minWidth: 180 }}
      />
    </Box>
  );
}
