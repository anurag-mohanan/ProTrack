import {
  Autocomplete,
  Box,
  Divider,
  FormControlLabel,
  IconButton,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FilterListIcon from '@mui/icons-material/FilterList';
import type { Customer, Team, User } from '../../../types';
import type { ExecutionStatus, ProjectStage } from '../../../types/common';
import { EXECUTION_STATUS_LABELS, PROJECT_STAGE_LABELS } from '../../../types/common';
import type { ProjectType } from '../../../types/ProjectTemplate';
import { FormField, FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { userDisplayName } from '../../../utils/format';
import {
  type ProjectCommandCenterFilters,
} from '../../../utils/projectCommandCenter';

interface ProjectFilterSidebarProps {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  draft: ProjectCommandCenterFilters;
  onDraftChange: (next: ProjectCommandCenterFilters) => void;
  onApply: () => void;
  onReset: () => void;
  onClear: () => void;
  customers: Customer[];
  teams: Team[];
  projectTypes: ProjectType[];
  users: User[];
}

const allOption = { value: 'all', label: 'All' };

export function ProjectFilterSidebar({
  collapsed,
  onToggleCollapsed,
  draft,
  onDraftChange,
  onApply,
  onReset,
  onClear,
  customers,
  teams,
  projectTypes,
  users,
}: ProjectFilterSidebarProps) {
  const selectedCustomers = customers.filter((customer) =>
    draft.customerIds.includes(customer.id),
  );
  const selectedTeams = teams.filter((team) => draft.teamIds.includes(team.id));
  const userOptions = users.map((user) => ({
    value: user.id,
    label: userDisplayName(user),
  }));

  if (collapsed) {
    return (
      <Paper
        variant="outlined"
        sx={{
          width: 48,
          flexShrink: 0,
          borderRadius: 3,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          py: 1,
        }}
      >
        <IconButton size="small" onClick={onToggleCollapsed} aria-label="Expand filters">
          <ChevronRightIcon />
        </IconButton>
        <FilterListIcon sx={{ fontSize: 18, color: 'text.secondary', mt: 1 }} />
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        width: 280,
        flexShrink: 0,
        borderRadius: 3,
        display: 'flex',
        flexDirection: 'column',
        maxHeight: 'calc(100vh - 220px)',
        position: 'sticky',
        top: 16,
      }}
    >
      <Box
        sx={{
          px: 2,
          py: 1.5,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FilterListIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Filters
          </Typography>
        </Box>
        <IconButton size="small" onClick={onToggleCollapsed} aria-label="Collapse filters">
          <ChevronLeftIcon />
        </IconButton>
      </Box>

      <Box sx={{ flex: 1, overflowY: 'auto', px: 2, py: 2 }}>
        <Stack spacing={2}>
          <FormField
            label="Search"
            value={draft.search}
            onChange={(event) => onDraftChange({ ...draft, search: event.target.value })}
            placeholder="Tool, customer, designer…"
          />

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
            renderInput={(params) => <TextField {...params} label="Customer" />}
          />

          <FormSelect
            label="Project Type"
            value={draft.projectTypeId}
            options={[
              allOption,
              ...projectTypes.map((type) => ({ value: type.id, label: type.name })),
            ]}
            onChange={(event) =>
              onDraftChange({ ...draft, projectTypeId: String(event.target.value) })
            }
          />

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
            renderInput={(params) => <TextField {...params} label="Team" />}
          />

          <FormSelect
            label="Stage"
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
          />

          <FormSelect
            label="Execution Status"
            value={draft.executionStatus}
            options={[
              { value: 'all', label: 'All Statuses' },
              ...(
                Object.entries(EXECUTION_STATUS_LABELS) as Array<[ExecutionStatus, string]>
              ).map(([value, label]) => ({ value, label })),
            ]}
            onChange={(event) =>
              onDraftChange({
                ...draft,
                executionStatus: event.target.value as ExecutionStatus | 'all',
              })
            }
          />

          <FormSelect
            label="Design Leader"
            searchable
            value={draft.designLeaderId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designLeaderId: String(event.target.value) })
            }
          />

          <FormSelect
            label="Designer"
            searchable
            value={draft.designerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designerId: String(event.target.value) })
            }
          />

          <FormSelect
            label="Surfacer"
            searchable
            value={draft.surfacerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, surfacerId: String(event.target.value) })
            }
          />

          <FormSelect
            label="Priority"
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
          />

          <FormSelect
            label="Due Date"
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
          />

          <FormControlLabel
            control={
              <Switch
                checked={draft.showArchived}
                onChange={(event) =>
                  onDraftChange({ ...draft, showArchived: event.target.checked })
                }
              />
            }
            label="Show Archived"
          />

          <FormControlLabel
            control={
              <Switch
                checked={draft.groupByTeam}
                onChange={(event) =>
                  onDraftChange({ ...draft, groupByTeam: event.target.checked })
                }
              />
            }
            label="Group By Team"
          />
        </Stack>
      </Box>

      <Divider />
      <Stack spacing={1} sx={{ p: 2 }}>
        <ProsohmButton buttonVariant="primary" size="small" onClick={onApply}>
          Apply
        </ProsohmButton>
        <ProsohmButton buttonVariant="outlined" size="small" onClick={onReset}>
          Reset
        </ProsohmButton>
        <ProsohmButton buttonVariant="outlined" size="small" onClick={onClear}>
          Clear Filters
        </ProsohmButton>
      </Stack>
    </Paper>
  );
}
