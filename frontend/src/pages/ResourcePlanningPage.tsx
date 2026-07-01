import { useMemo, useState } from 'react';
import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { useTheme } from '@mui/material/styles';
import { fetchTeamResourcePlanning } from '../api/dashboard';
import { fetchTeams } from '../api/lookups';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { prosohmDataGridSx } from '../theme/componentStyles';
import type { TeamResourcePlanningRow } from '../types/Team';
import { formatNumber } from '../utils/format';

export function ResourcePlanningPage() {
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const teamParam = teamFilter === 'all' ? undefined : teamFilter;

  const teamsQuery = useQuery({
    queryKey: ['lookups', 'teams'],
    queryFn: fetchTeams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const planningQuery = useQuery({
    queryKey: ['resource-planning', teamParam],
    queryFn: () => fetchTeamResourcePlanning(teamParam),
    staleTime: QUERY_STALE_TIMES.dashboard,
  });

  const columns: GridColDef<TeamResourcePlanningRow>[] = [
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
      width: 120,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'allocated_hours',
      headerName: 'Allocated',
      width: 120,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'actual_hours',
      headerName: 'Actual',
      width: 120,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'remaining_capacity_hours',
      headerName: 'Remaining',
      width: 120,
      valueFormatter: (value) => formatNumber(Number(value)),
    },
    {
      field: 'utilization_percent',
      headerName: 'Utilization %',
      width: 130,
      valueFormatter: (value) => `${formatNumber(Number(value))}%`,
    },
  ];

  if (planningQuery.isLoading) return <LoadingState message="Loading resource planning…" />;
  if (planningQuery.error) return <ErrorState error={planningQuery.error} />;

  return (
    <Box>
      <PageHeader
        title="Resource Planning"
        subtitle="Team capacity, allocation, and utilization"
      />

      <Box sx={{ mb: 2.5 }}>
        <ContentCard>
          <FormControl sx={{ minWidth: 240 }}>
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
        </ContentCard>
      </Box>

      <ContentCard noPadding>
        <DataGrid
          rows={planningQuery.data ?? []}
          columns={columns}
          getRowId={(row) => row.team_id}
          autoHeight
          sx={gridSx}
        />
      </ContentCard>
    </Box>
  );
}
