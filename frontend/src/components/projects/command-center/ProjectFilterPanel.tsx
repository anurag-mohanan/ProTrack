import type { ReactNode } from 'react';
import {
  Autocomplete,
  Box,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import type { Customer, Team, User } from '../../../types';
import type { ProjectStage } from '../../../types/common';
import { PROJECT_STAGE_LABELS } from '../../../types/common';
import type { ProjectType } from '../../../types/ProjectTemplate';
import { FormSelect } from '../../ui/design-system';
import { FilterGroup } from '../../ui/design-system/filters';
import { compactFilterFieldSx } from '../../ui/design-system/filters/filterFieldStyles';
import { type ProjectCommandCenterFilters } from '../../../utils/projectCommandCenter';

interface ProjectFilterPanelProps {
  draft: ProjectCommandCenterFilters;
  onDraftChange: (next: ProjectCommandCenterFilters) => void;
  customers: Customer[];
  teams: Team[];
  projectTypes: ProjectType[];
  users: User[];
}

const allOption = { value: 'all', label: 'All' };

export function ProjectFilterPanel({
  draft,
  onDraftChange,
  customers,
  teams,
  projectTypes,
  users,
}: ProjectFilterPanelProps) {
  const selectedCustomers = customers.filter((customer) =>
    draft.customerIds.includes(customer.id),
  );
  const selectedTeams = teams.filter((team) => draft.teamIds.includes(team.id));
  const userOptions = users.map((user) => ({
    value: user.id,
    label: `${user.first_name} ${user.last_name}`.trim() || user.email,
  }));

  const field = (node: ReactNode) => <Box sx={compactFilterFieldSx}>{node}</Box>;

  return (
    <Stack spacing={0.5}>
      <Box sx={{ pb: 1 }}>
        <Typography
          variant="caption"
          sx={{ fontWeight: 700, color: 'text.secondary', mb: 0.75, display: 'block' }}
        >
          Primary filters
        </Typography>
        <Stack spacing={1}>
          {field(
            <Autocomplete
              multiple
              size="small"
              options={customers}
              value={selectedCustomers}
              getOptionLabel={(option) => option.name}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              onChange={(_, next) =>
                onDraftChange({ ...draft, customerIds: next.map((customer) => customer.id) })
              }
              renderInput={(params) => <TextField {...params} label="Customer" size="small" />}
            />,
          )}
          {field(
            <FormSelect
              label="Status"
              size="small"
              value={draft.executionStatus}
              options={[
                { value: 'all', label: 'All Statuses' },
                { value: 'planning', label: 'Planning' },
                { value: 'currently_being_worked_on', label: 'In Progress' },
                { value: 'on_hold', label: 'On Hold' },
                { value: 'completed', label: 'Completed' },
                { value: 'cancelled', label: 'Cancelled' },
              ]}
              onChange={(event) =>
                onDraftChange({
                  ...draft,
                  executionStatus: event.target.value as ProjectCommandCenterFilters['executionStatus'],
                })
              }
            />,
          )}
          {field(
            <FormSelect
              label="Stage"
              size="small"
              value={draft.projectStage}
              options={[
                { value: 'all', label: 'All Stages' },
                ...(
                  Object.entries(PROJECT_STAGE_LABELS) as Array<[ProjectStage, string]>
                ).map(([value, label]) => ({ value, label })),
              ]}
              onChange={(event) =>
                onDraftChange({
                  ...draft,
                  projectStage: event.target.value as ProjectStage | 'all',
                })
              }
            />,
          )}
          {field(
            <FormSelect
              label="Designer"
              searchable
              size="small"
              value={draft.designerId}
              options={[allOption, ...userOptions]}
              onChange={(event) =>
                onDraftChange({ ...draft, designerId: String(event.target.value) })
              }
            />,
          )}
        </Stack>
      </Box>

      <FilterGroup title="Project" icon={<FolderOutlinedIcon sx={{ fontSize: 14 }} />}>
        {field(
          <FormSelect
            label="Project Type"
            size="small"
            value={draft.projectTypeId}
            options={[
              allOption,
              ...projectTypes.map((type) => ({ value: type.id, label: type.name })),
            ]}
            onChange={(event) =>
              onDraftChange({ ...draft, projectTypeId: String(event.target.value) })
            }
          />,
        )}
      </FilterGroup>

      <FilterGroup title="Team" icon={<GroupsOutlinedIcon sx={{ fontSize: 14 }} />}>
        {field(
          <Autocomplete
            multiple
            size="small"
            options={teams}
            value={selectedTeams}
            getOptionLabel={(option) => option.name}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            onChange={(_, next) =>
              onDraftChange({ ...draft, teamIds: next.map((team) => team.id) })
            }
            renderInput={(params) => <TextField {...params} label="Team" size="small" />}
          />,
        )}
        {field(
          <FormSelect
            label="Business unit"
            size="small"
            value={draft.businessUnit}
            options={[
              allOption,
              ...Array.from(
                new Set(
                  teams
                    .map((team) => team.business_unit?.trim())
                    .filter((value): value is string => Boolean(value)),
                ),
              )
                .sort()
                .map((value) => ({ value, label: value })),
            ]}
            onChange={(event) =>
              onDraftChange({ ...draft, businessUnit: String(event.target.value) })
            }
          />,
        )}
        {field(
          <FormSelect
            label="Design Leader"
            searchable
            size="small"
            value={draft.designLeaderId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designLeaderId: String(event.target.value) })
            }
          />,
        )}
        {field(
          <FormSelect
            label="Surfacer"
            searchable
            size="small"
            value={draft.surfacerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, surfacerId: String(event.target.value) })
            }
          />,
        )}
      </FilterGroup>

      <FilterGroup title="Planning" icon={<CalendarMonthOutlinedIcon sx={{ fontSize: 14 }} />}>
        {field(
          <FormSelect
            label="Priority"
            size="small"
            value={draft.priority}
            options={[
              { value: 'all', label: 'All Priorities' },
              { value: 'critical', label: 'Critical' },
              { value: 'high', label: 'High' },
              { value: 'medium', label: 'Medium' },
              { value: 'low', label: 'Low' },
            ]}
            onChange={(event) =>
              onDraftChange({
                ...draft,
                priority: event.target.value as ProjectCommandCenterFilters['priority'],
              })
            }
          />,
        )}
        {field(
          <FormSelect
            label="Health"
            size="small"
            value={draft.health}
            options={[
              { value: 'all', label: 'All Health' },
              { value: 'green', label: 'Green' },
              { value: 'yellow', label: 'Amber' },
              { value: 'red', label: 'Red' },
            ]}
            onChange={(event) =>
              onDraftChange({
                ...draft,
                health: event.target.value as ProjectCommandCenterFilters['health'],
              })
            }
          />,
        )}
        {field(
          <FormSelect
            label="Due Date"
            size="small"
            value={draft.dueDate}
            options={[
              { value: 'all', label: 'Any due date' },
              { value: 'week', label: 'Due this week' },
              { value: '7days', label: 'Due next 7 days' },
              { value: 'overdue', label: 'Overdue' },
            ]}
            onChange={(event) =>
              onDraftChange({
                ...draft,
                dueDate: event.target.value as ProjectCommandCenterFilters['dueDate'],
              })
            }
          />,
        )}
        <FormControlLabel
          sx={{ ml: 0, mr: 0 }}
          control={
            <Switch
              size="small"
              checked={draft.showArchived}
              onChange={(event) =>
                onDraftChange({ ...draft, showArchived: event.target.checked })
              }
            />
          }
          label={<Typography variant="caption">Show archived</Typography>}
        />
      </FilterGroup>
    </Stack>
  );
}
