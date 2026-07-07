import {
  Autocomplete,
  Box,
  Chip,
  Divider,
  FormControlLabel,
  IconButton,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FilterListIcon from '@mui/icons-material/FilterList';
import type { Customer, Team, User } from '../../../types';
import type { ProjectStage } from '../../../types/common';
import { PROJECT_STAGE_LABELS } from '../../../types/common';
import type { ProjectType } from '../../../types/ProjectTemplate';
import { FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { type ProjectCommandCenterFilters } from '../../../utils/projectCommandCenter';

interface ProjectFilterSidebarProps {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  draft: ProjectCommandCenterFilters;
  activeFilterCount: number;
  onDraftChange: (next: ProjectCommandCenterFilters) => void;
  onApply: () => void;
  onReset: () => void;
  onClear: () => void;
  customers: Customer[];
  teams: Team[];
  projectTypes: ProjectType[];
  users: User[];
  embedded?: boolean;
}

const allOption = { value: 'all', label: 'All' };

const roundedControlSx = {
  '& .MuiOutlinedInput-root': {
    borderRadius: 2,
  },
  '& .MuiInputBase-root': { minHeight: 40 },
  '& .MuiInputLabel-root': { fontSize: '0.8125rem' },
};

export function ProjectFilterSidebar({
  collapsed,
  onToggleCollapsed,
  draft,
  activeFilterCount,
  onDraftChange,
  onApply,
  onReset,
  onClear,
  customers,
  teams,
  projectTypes,
  users,
  embedded = false,
}: ProjectFilterSidebarProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const selectedCustomers = customers.filter((customer) =>
    draft.customerIds.includes(customer.id),
  );
  const selectedTeams = teams.filter((team) => draft.teamIds.includes(team.id));
  const userOptions = users.map((user) => ({
    value: user.id,
    label: `${user.first_name} ${user.last_name}`.trim() || user.email,
  }));

  if (collapsed && !embedded) {
    return (
      <Paper
        variant="outlined"
        sx={{
          width: 44,
          flexShrink: 0,
          borderRadius: 2.5,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          py: 1,
        }}
      >
        <IconButton size="small" onClick={onToggleCollapsed} aria-label="Expand filters">
          <ChevronRightIcon fontSize="small" />
        </IconButton>
        <FilterListIcon sx={{ fontSize: 16, color: 'text.secondary', mt: 0.5 }} />
        {activeFilterCount > 0 ? (
          <Chip label={activeFilterCount} size="small" color="primary" sx={{ mt: 1, minWidth: 24, height: 20 }} />
        ) : null}
      </Paper>
    );
  }

  const content = (
    <>
      {!embedded ? (
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
              Filters{activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
            </Typography>
          </Box>
          {!isMobile ? (
            <IconButton size="small" onClick={onToggleCollapsed} aria-label="Collapse filters">
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          ) : null}
        </Box>
      ) : null}

      <Box sx={{ flex: 1, overflowY: 'auto', px: 2, py: 1.5 }}>
        <Stack spacing={1.5}>
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
            renderInput={(params) => (
              <TextField {...params} label="Customer" size="small" sx={roundedControlSx} />
            )}
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
            sx={roundedControlSx}
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
            renderInput={(params) => (
              <TextField {...params} label="Team" size="small" sx={roundedControlSx} />
            )}
          />

          <FormSelect
            label="Project Stage"
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
            sx={roundedControlSx}
          />

          <FormSelect
            label="Design Leader"
            searchable
            value={draft.designLeaderId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designLeaderId: String(event.target.value) })
            }
            sx={roundedControlSx}
          />

          <FormSelect
            label="Designer"
            searchable
            value={draft.designerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designerId: String(event.target.value) })
            }
            sx={roundedControlSx}
          />

          <FormSelect
            label="Surfacer"
            searchable
            value={draft.surfacerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, surfacerId: String(event.target.value) })
            }
            sx={roundedControlSx}
          />

          <FormSelect
            label="Project Status"
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
            sx={roundedControlSx}
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
            sx={roundedControlSx}
          />

          <FormSelect
            label="Health"
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
            sx={roundedControlSx}
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
            sx={roundedControlSx}
          />

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
            label={<Typography variant="body2">Show Archived</Typography>}
          />
        </Stack>
      </Box>

      <Divider />
      <Stack spacing={1} sx={{ p: 2 }}>
        <ProsohmButton buttonVariant="primary" size="small" onClick={onApply}>
          Apply Filters
        </ProsohmButton>
        <ProsohmButton buttonVariant="outlined" size="small" onClick={onClear}>
          Clear Filters
        </ProsohmButton>
        <ProsohmButton buttonVariant="outlined" size="small" onClick={onReset}>
          Reset Filters
        </ProsohmButton>
      </Stack>
    </>
  );

  if (embedded) {
    return <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>{content}</Box>;
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        width: { xs: '100%', lg: 300 },
        flexShrink: 0,
        borderRadius: 2.5,
        display: { xs: 'none', md: 'flex' },
        flexDirection: 'column',
        maxHeight: 'calc(100vh - 120px)',
        position: 'sticky',
        top: 12,
        boxShadow: (t) => t.palette.prosohm.shadowCard,
      }}
    >
      {content}
    </Paper>
  );
}
