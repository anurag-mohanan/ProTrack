import { useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Tab,
  Tabs,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  assignProjectDesigner,
  fetchResourcePlanningGrid,
  resourcePlanningQueryKeys,
} from '../api/resourcePlanning';
import { fetchDepartments } from '../api/settings';
import { fetchTeams } from '../api/lookups';
import {
  ResourcePlanningLeftPanel,
  type LeftPanelTab,
} from '../components/resource-planning/ResourcePlanningLeftPanel';
import { ResourcePlanningRightPanel } from '../components/resource-planning/ResourcePlanningRightPanel';
import { ResourcePlanningTimeline } from '../components/resource-planning/ResourcePlanningTimeline';
import { PageContainer } from '../components/common/PageContainer';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { KpiMetricCard, ModernPageHeader } from '../components/ui/design-system';
import { KpiStrip } from '../components/analytics/KpiStrip';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useToast } from '../context/ToastContext';
import type { ResourcePlanningGranularity } from '../types/ResourcePlanning';
import { formatNumber } from '../utils/format';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';

const GRANULARITY_OPTIONS: { value: ResourcePlanningGranularity; label: string }[] = [
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
  { value: 'day', label: 'Daily' },
];

export function ResourcePlanningPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [teamFilter, setTeamFilter] = useState<string>('all');
  const [granularity, setGranularity] = useState<ResourcePlanningGranularity>('week');
  const [leftTab, setLeftTab] = useState<LeftPanelTab>('designers');
  const [selectedDesignerId, setSelectedDesignerId] = useState<string | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

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

  const departmentsQuery = useQuery({
    queryKey: ['settings', 'departments'],
    queryFn: fetchDepartments,
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

  if (planningQuery.isLoading) return <LoadingState message="Loading resource planning…" />;
  if (planningQuery.error) return <ErrorState error={planningQuery.error} />;
  if (!planningQuery.data) return null;

  const data = planningQuery.data;
  const filteredByTeam = selectedTeamId
    ? {
        ...data,
        designers: data.designers.filter((d) =>
          data.team_summary.some(
            (t) => t.team_id === selectedTeamId && d.team_name === t.team_name,
          ),
        ),
      }
    : data;

  const totalCapacity = data.designers.reduce((sum, d) => sum + d.capacity_hours, 0);
  const totalAllocated = data.designers.reduce((sum, d) => sum + d.allocated_hours, 0);
  const avgUtil =
    totalCapacity > 0 ? Math.round((totalAllocated / totalCapacity) * 100) : 0;
  const overloaded = data.designers.filter(
    (d) => d.capacity_hours > 0 && d.allocated_hours / d.capacity_hours >= 0.9,
  ).length;

  return (
    <PageContainer>
      <ModernPageHeader
        title="Resource Planning"
        subtitle="Engineering planning dashboard — capacity, assignments, and customer allocation"
        actions={
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 180 }}>
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
              sx={{ minHeight: 40 }}
            >
              {GRANULARITY_OPTIONS.map((option) => (
                <Tab key={option.value} value={option.value} label={option.label} sx={{ minHeight: 40 }} />
              ))}
            </Tabs>
          </Box>
        }
        summary={
          <KpiStrip columns={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              compact
              title="Designers"
              value={String(data.designers.length)}
              icon={GroupsRoundedIcon}
              accent="primary"
            />
            <KpiMetricCard
              compact
              title="Avg Utilization"
              value={`${avgUtil}%`}
              icon={TrendingUpRoundedIcon}
              accent={avgUtil >= 90 ? 'error' : avgUtil >= 75 ? 'warning' : 'success'}
            />
            <KpiMetricCard
              compact
              title="Allocated Hours"
              value={formatNumber(totalAllocated)}
              subtitle={`of ${formatNumber(totalCapacity)}h capacity`}
              icon={ScheduleRoundedIcon}
              accent="info"
            />
            <KpiMetricCard
              compact
              title="Near / Over Capacity"
              value={String(overloaded)}
              icon={WarningAmberRoundedIcon}
              accent="warning"
            />
          </KpiStrip>
        }
      />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '280px 1fr 300px' },
          gap: 2,
          height: { lg: 'calc(100vh - 280px)' },
          minHeight: 520,
        }}
      >
        <ResourcePlanningLeftPanel
          tab={leftTab}
          onTabChange={setLeftTab}
          designers={filteredByTeam.designers}
          teams={data.team_summary}
          departments={departmentsQuery.data ?? []}
          selectedDesignerId={selectedDesignerId}
          selectedTeamId={selectedTeamId}
          onSelectDesigner={setSelectedDesignerId}
          onSelectTeam={setSelectedTeamId}
        />

        <Box sx={{ minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <ResourcePlanningTimeline
            grid={filteredByTeam}
            selectedDesignerId={selectedDesignerId}
            selectedProjectId={selectedProjectId}
            onAssign={(projectId, designerId) =>
              assignMutation.mutate({ project_id: projectId, designer_id: designerId })
            }
            onSelectProject={setSelectedProjectId}
          />
        </Box>

        <ResourcePlanningRightPanel
          grid={data}
          selectedDesignerId={selectedDesignerId}
          selectedProjectId={selectedProjectId}
          onSelectProject={setSelectedProjectId}
        />
      </Box>
    </PageContainer>
  );
}
