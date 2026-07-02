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
import { FormField, FormSelect } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { userDisplayName } from '../../../utils/format';
import { type ProjectCommandCenterFilters } from '../../../utils/projectCommandCenter';

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
  embedded?: boolean;
}

const allOption = { value: 'all', label: 'All' };

const compactFieldSx = {
  '& .MuiInputBase-root': { minHeight: 40 },
  '& .MuiInputLabel-root': { fontSize: '0.8125rem' },
};

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
    label: userDisplayName(user),
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
      </Paper>
    );
  }

  const content = (
    <>
      {!embedded ? (
        <Box
          sx={{
            px: 1.5,
            py: 1.25,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <FilterListIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.8125rem' }}>
              Filters
            </Typography>
          </Box>
          {!isMobile ? (
            <IconButton size="small" onClick={onToggleCollapsed} aria-label="Collapse filters">
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          ) : null}
        </Box>
      ) : null}

      <Box sx={{ flex: 1, overflowY: 'auto', px: 1.5, py: 1.5 }}>
        <Stack spacing={1.25}>
          <FormField
            label="Search"
            size="small"
            value={draft.search}
            onChange={(event) => onDraftChange({ ...draft, search: event.target.value })}
            placeholder="Tool, customer, designer…"
            sx={compactFieldSx}
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
            renderInput={(params) => <TextField {...params} label="Customer" size="small" />}
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
            sx={compactFieldSx}
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
            renderInput={(params) => <TextField {...params} label="Team" size="small" />}
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
            sx={compactFieldSx}
          />

          <FormSelect
            label="Design Leader"
            searchable
            value={draft.designLeaderId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designLeaderId: String(event.target.value) })
            }
            sx={compactFieldSx}
          />

          <FormSelect
            label="Designer"
            searchable
            value={draft.designerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, designerId: String(event.target.value) })
            }
            sx={compactFieldSx}
          />

          <FormSelect
            label="Surfacer"
            searchable
            value={draft.surfacerId}
            options={[allOption, ...userOptions]}
            onChange={(event) =>
              onDraftChange({ ...draft, surfacerId: String(event.target.value) })
            }
            sx={compactFieldSx}
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
            sx={compactFieldSx}
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
      <Stack spacing={0.75} sx={{ p: 1.5 }}>
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
        width: { xs: '100%', lg: 290 },
        flexShrink: 0,
        borderRadius: 2.5,
        display: { xs: 'none', md: 'flex' },
        flexDirection: 'column',
        maxHeight: 'calc(100vh - 120px)',
        position: 'sticky',
        top: 12,
      }}
    >
      {content}
    </Paper>
  );
}
