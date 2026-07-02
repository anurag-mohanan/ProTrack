import { useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { useTheme } from '@mui/material/styles';
import {
  assignProjectDesigner,
  fetchResourcePlanningGrid,
  resourcePlanningQueryKeys,
} from '../api/resourcePlanning';
import { fetchTeams } from '../api/lookups';
import { ResourcePlanningGridView } from '../components/resource-planning/ResourcePlanningGridView';
import { PageContainer } from '../components/common/PageContainer';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useToast } from '../context/ToastContext';
import { prosohmDataGridSx } from '../theme/componentStyles';
import type { ResourcePlanningGranularity } from '../types/ResourcePlanning';
import type { TeamResourcePlanningRow } from '../types/Team';
import { formatNumber } from '../utils/format';

const GRANULARITY_OPTIONS: { value: ResourcePlanningGranularity; label: string }[] = [
  { value: 'day', label: 'Daily' },
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
];

export function ResourcePlanningPage() {
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const [granularity, setGranularity] = useState<ResourcePlanningGranularity>('week');
  const teamParam = teamFilter === 'all' ? undefined : teamFilter;

  const gridParams = useMemo(
    () => ({ granularity, team_id: teamParam }),
    [granularity, teamParam],
  );

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const planningQuery = useQuery({
    queryKey: resourcePlanningQueryKeys.grid(gridParams),
    queryFn: () => fetchResourcePlanningGrid(gridParams),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const assignMutation = useMutation({
    mutationFn: assignProjectDesigner,
    onSuccess: () => {
      showSuccess('Project assignment updated');
      void queryClient.invalidateQueries({ queryKey: ['resource-planning'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const summaryColumns: GridColDef<TeamResourcePlanningRow>[] = [
    {
      field: 'team_name',
      headerName: 'Team',
      flex: 1.2,
      minWidth: 160,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: params.row.team_colour,
            }}
          />
          {params.value}
        </Box>
      ),
    },
    { field: 'member_count', headerName: 'Members', width: 100 },
    {
      field: 'capacity_hours',
      headerName: 'Capacity',
      width: 110,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'allocated_hours',
      headerName: 'Allocated',
      width: 110,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'remaining_capacity_hours',
      headerName: 'Remaining',
      width: 110,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'utilization_percent',
      headerName: 'Utilization',
      width: 110,
      valueFormatter: (value) => `${formatNumber(Number(value))}%`,
    },
  ];

  if (planningQuery.isLoading) return <LoadingState message="Loading resource planning…" />;
  if (planningQuery.error) return <ErrorState error={planningQuery.error} />;
  if (!planningQuery.data) return null;

  const data = planningQuery.data;

  return (
    <PageContainer>
      <PageHeader
        title="Resource Planning"
        subtitle="Designer capacity across daily, weekly, and monthly horizons"
      />

      <Box sx={{ mb: 2.5 }}>
        <ContentCard>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
          <FormControl sx={{ minWidth: 220 }}>
            <InputLabel>Team</InputLabel>
            <Select
              label="Team"
              value={teamFilter}
              onChange={(event) => setTeamFilter(String(event.target.value))}
            >
              <MenuItem value="all">All Teams</MenuItem>
              {(teamsQuery.data ?? []).map((team) => (
                <MenuItem key={team.id} value={team.id}>
                  {team.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tabs
            value={granularity}
            onChange={(_, value: ResourcePlanningGranularity) => setGranularity(value)}
          >
            {GRANULARITY_OPTIONS.map((option) => (
              <Tab key={option.value} value={option.value} label={option.label} />
            ))}
          </Tabs>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 2 }}>
          {(['green', 'blue', 'orange', 'red', 'grey'] as const).map((color) => (
            <Typography key={color} variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  bgcolor:
                    color === 'grey'
                      ? 'text.disabled'
                      : `${color}.main`,
                }}
              />
              {color.charAt(0).toUpperCase() + color.slice(1)}
            </Typography>
          ))}
        </Box>
        </ContentCard>
      </Box>

      <Box sx={{ mb: 2.5 }}>
        <ContentCard title="Team Summary" noPadding>
          <DataGrid
            rows={data.team_summary}
            columns={summaryColumns}
            getRowId={(row) => row.team_id}
            autoHeight
            hideFooter
            sx={gridSx}
          />
        </ContentCard>
      </Box>

      <ResourcePlanningGridView
        grid={data}
        onAssign={(projectId, designerId) =>
          assignMutation.mutate({ project_id: projectId, designer_id: designerId })
        }
      />
    </PageContainer>
  );
}
