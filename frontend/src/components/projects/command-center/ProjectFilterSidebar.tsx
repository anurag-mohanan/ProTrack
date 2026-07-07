import type { ReactNode } from 'react';
import {
  Autocomplete,
  Box,
  Chip,
  Collapse,
  Divider,
  FormControlLabel,
  Grid,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import KeyboardArrowRightRoundedIcon from '@mui/icons-material/KeyboardArrowRightRounded';
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded';
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
  const selectedCustomers = customers.filter((customer) =>
    draft.customerIds.includes(customer.id),
  );
  const selectedTeams = teams.filter((team) => draft.teamIds.includes(team.id));
  const userOptions = users.map((user) => ({
    value: user.id,
    label: `${user.first_name} ${user.last_name}`.trim() || user.email,
  }));

  const compactControlSx = {
    '& .MuiOutlinedInput-root': {
      borderRadius: 2,
      minHeight: 36,
    },
    '& .MuiInputBase-root': {
      minHeight: 36,
      fontSize: '0.8125rem',
    },
    '& .MuiInputLabel-root': {
      fontSize: '0.75rem',
      mt: -0.2,
    },
  };

  const sectionSx = {
    p: 1.25,
    borderRadius: 2,
    bgcolor: 'rgba(15, 23, 42, 0.02)',
    border: '1px solid',
    borderColor: 'divider',
  };

  const sectionHeader = (
    icon: ReactNode,
    title: string,
  ) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1 }}>
      {icon}
      <Typography variant="caption" sx={{ fontWeight: 800, letterSpacing: '0.03em' }}>
        {title}
      </Typography>
    </Box>
  );

  const content = (
    <>
      <Box
        sx={{
          px: 1.5,
          py: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          position: 'sticky',
          top: 0,
          zIndex: 2,
        }}
      >
        <Chip
          icon={<FilterListIcon sx={{ fontSize: 16 }} />}
          label={`Filters${activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}`}
          size="small"
          onClick={onToggleCollapsed}
          deleteIcon={
            collapsed ? <KeyboardArrowRightRoundedIcon /> : <KeyboardArrowDownRoundedIcon />
          }
          onDelete={onToggleCollapsed}
          variant="outlined"
          sx={{ borderRadius: 1.5, fontWeight: 700 }}
        />
      </Box>

      <Collapse in={!collapsed} timeout="auto">
        <Box sx={{ flex: 1, overflowY: 'auto', px: 1.25, py: 1 }}>
          <Stack spacing={1}>
            <Box sx={sectionSx}>
              {sectionHeader(<FolderOutlinedIcon sx={{ fontSize: 15 }} />, 'Project')}
              <Grid container spacing={0.75}>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                      <TextField {...params} label="Customer" size="small" sx={compactControlSx} />
                    )}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                    sx={compactControlSx}
                  />
                </Grid>
              </Grid>
            </Box>

            <Box sx={sectionSx}>
              {sectionHeader(<GroupsOutlinedIcon sx={{ fontSize: 15 }} />, 'Team')}
              <Grid container spacing={0.75}>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                      <TextField {...params} label="Team" size="small" sx={compactControlSx} />
                    )}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormSelect
                    label="Design Leader"
                    searchable
                    size="small"
                    value={draft.designLeaderId}
                    options={[allOption, ...userOptions]}
                    onChange={(event) =>
                      onDraftChange({ ...draft, designLeaderId: String(event.target.value) })
                    }
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormSelect
                    label="Designer"
                    searchable
                    size="small"
                    value={draft.designerId}
                    options={[allOption, ...userOptions]}
                    onChange={(event) =>
                      onDraftChange({ ...draft, designerId: String(event.target.value) })
                    }
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormSelect
                    label="Surfacer"
                    searchable
                    size="small"
                    value={draft.surfacerId}
                    options={[allOption, ...userOptions]}
                    onChange={(event) =>
                      onDraftChange({ ...draft, surfacerId: String(event.target.value) })
                    }
                    sx={compactControlSx}
                  />
                </Grid>
              </Grid>
            </Box>

            <Box sx={sectionSx}>
              {sectionHeader(<CalendarMonthOutlinedIcon sx={{ fontSize: 15 }} />, 'Planning')}
              <Grid container spacing={0.75}>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
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
                    sx={compactControlSx}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormControlLabel
                    sx={{ ml: 0, mr: 0, mt: 0.5 }}
                    control={
                      <Switch
                        size="small"
                        checked={draft.showArchived}
                        onChange={(event) =>
                          onDraftChange({ ...draft, showArchived: event.target.checked })
                        }
                      />
                    }
                    label={<Typography variant="caption">Show Archived</Typography>}
                  />
                </Grid>
              </Grid>
            </Box>
          </Stack>
        </Box>
      </Collapse>

      <Divider />
      <Stack direction="row" spacing={0.75} sx={{ p: 1.25 }}>
        <ProsohmButton buttonVariant="primary" size="small" onClick={onApply} sx={{ flex: 1 }}>
          Apply
        </ProsohmButton>
        <ProsohmButton buttonVariant="outlined" size="small" onClick={onClear} sx={{ flex: 1 }}>
          Clear
        </ProsohmButton>
      </Stack>
      {activeFilterCount > 0 ? (
        <Stack sx={{ px: 1.25, pb: 1.25 }}>
          <ProsohmButton buttonVariant="outlined" size="small" onClick={onReset}>
            Reset Filters
          </ProsohmButton>
        </Stack>
      ) : null}
      {embedded ? null : (
        <Stack sx={{ px: 1.25, pb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Click the filter chip to collapse/expand.
          </Typography>
        </Stack>
      )}
    </>
  );

  if (embedded) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.paper' }}>
        {content}
      </Box>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        width: 220,
        flexShrink: 0,
        borderRadius: 2.5,
        display: { xs: 'none', lg: 'flex' },
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
