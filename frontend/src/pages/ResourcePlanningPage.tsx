import { useMemo, useState } from 'react';
import { Box, Tab, Tabs } from '@mui/material';
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
import {
  FilterDrawer,
  FilterGroup,
  FilterToolbar,
  FormSelect,
  KpiMetricCard,
  ModernPageHeader,
  compactFilterFieldSx,
} from '../components/ui/design-system';
import { KpiStrip } from '../components/analytics/KpiStrip';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useToast } from '../context/ToastContext';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { fetchAssignmentSkillFit } from '../api/assignmentSkillFit';
import { getErrorMessage } from '../api/client';
import type { ResourcePlanningGranularity } from '../types/ResourcePlanning';
import { formatNumber, toFiniteNumber } from '../utils/format';
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';

const GRANULARITY_OPTIONS: { value: ResourcePlanningGranularity; label: string }[] = [
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
  { value: 'day', label: 'Daily' },
];

export function ResourcePlanningPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [appliedTeamFilter, setAppliedTeamFilter] = useState('all');
  const [draftTeamFilter, setDraftTeamFilter] = useState('all');
  const [appliedGranularity, setAppliedGranularity] = useState<ResourcePlanningGranularity>('week');
  const [draftGranularity, setDraftGranularity] = useState<ResourcePlanningGranularity>('week');
  const [leftTab, setLeftTab] = useState<LeftPanelTab>('designers');
  const [selectedDesignerId, setSelectedDesignerId] = useState<string | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  const teamParam = appliedTeamFilter === 'all' ? undefined : appliedTeamFilter;
  const gridParams = useMemo(
    () => ({ granularity: appliedGranularity, team_id: teamParam }),
    [appliedGranularity, teamParam],
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

  const [pendingAssign, setPendingAssign] = useState<{
    project_id: string;
    designer_id: string;
    message: string;
  } | null>(null);

  const assignMutation = useMutation({
    mutationFn: assignProjectDesigner,
    onSuccess: () => {
      showSuccess('Project assignment updated');
      setPendingAssign(null);
      void queryClient.invalidateQueries({ queryKey: ['resource-planning'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const requestAssign = async (projectId: string, designerId: string) => {
    const data = planningQuery.data;
    const fromUnassigned = data?.unassigned_projects?.find((row) => row.project_id === projectId);
    let complexity = fromUnassigned?.complexity ?? null;
    if (!complexity && data?.designers) {
      for (const designer of data.designers) {
        for (const cell of designer.cells ?? []) {
          const block = cell.blocks?.find((row) => row.project_id === projectId);
          if (block?.complexity) {
            complexity = block.complexity;
            break;
          }
        }
        if (complexity) break;
      }
    }
    try {
      const fit = await fetchAssignmentSkillFit({
        complexity: complexity || 'medium',
        user_id: designerId,
        role: 'designer',
      });
      if (fit.requires_confirmation) {
        setPendingAssign({
          project_id: projectId,
          designer_id: designerId,
          message: fit.message,
        });
        return;
      }
      assignMutation.mutate({ project_id: projectId, designer_id: designerId });
    } catch (error: unknown) {
      showError(getErrorMessage(error));
    }
  };

  const teamNameMap = useMemo(
    () => new Map((teamsQuery.data ?? []).map((team) => [team.id, team.name])),
    [teamsQuery.data],
  );

  const activeFilterCount =
    (appliedTeamFilter !== 'all' ? 1 : 0) + (appliedGranularity !== 'week' ? 1 : 0);

  const filterChips = useMemo(() => {
    const chips = [];
    if (appliedTeamFilter !== 'all') {
      chips.push({
        key: 'team',
        label: `Team: ${teamNameMap.get(appliedTeamFilter) ?? 'Unknown'}`,
        onRemove: () => {
          setAppliedTeamFilter('all');
          setDraftTeamFilter('all');
        },
      });
    }
    if (appliedGranularity !== 'week') {
      chips.push({
        key: 'granularity',
        label: `View: ${GRANULARITY_OPTIONS.find((option) => option.value === appliedGranularity)?.label ?? appliedGranularity}`,
        onRemove: () => {
          setAppliedGranularity('week');
          setDraftGranularity('week');
        },
      });
    }
    return chips;
  }, [appliedGranularity, appliedTeamFilter, teamNameMap]);

  const applyFilters = () => {
    setAppliedTeamFilter(draftTeamFilter);
    setAppliedGranularity(draftGranularity);
  };

  const resetFilters = () => {
    setDraftTeamFilter('all');
    setDraftGranularity('week');
  };

  const clearFilters = () => {
    setAppliedTeamFilter('all');
    setDraftTeamFilter('all');
    setAppliedGranularity('week');
    setDraftGranularity('week');
  };

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

  const totalCapacity = data.designers.reduce((sum, d) => sum + toFiniteNumber(d.capacity_hours), 0);
  const totalAllocated = data.designers.reduce((sum, d) => sum + toFiniteNumber(d.allocated_hours), 0);
  const avgUtil =
    totalCapacity > 0 ? Math.round((totalAllocated / totalCapacity) * 100) : 0;
  const overloaded = data.designers.filter((d) => {
    const capacity = toFiniteNumber(d.capacity_hours);
    const allocated = toFiniteNumber(d.allocated_hours);
    return capacity > 0 && allocated / capacity >= 0.9;
  }).length;

  return (
    <PageContainer>
      <ModernPageHeader
        title="Resource Planning"
        subtitle="Engineering planning dashboard — capacity, assignments, and customer allocation"
      />

      <Box sx={{ mb: 2.5 }}>
        <KpiStrip columns={4}>
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
            value={formatNumber(totalAllocated, 0) || '0'}
            subtitle={`of ${formatNumber(totalCapacity, 0) || '0'}h capacity`}
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
      </Box>

      <FilterToolbar
        sticky
        filterButton={{ activeCount: activeFilterCount, onClick: () => setFiltersOpen(true) }}
        chips={filterChips}
        onClearAll={clearFilters}
      >
        <Tabs
          value={appliedGranularity}
          onChange={(_, value: ResourcePlanningGranularity) => {
            setAppliedGranularity(value);
            setDraftGranularity(value);
          }}
          sx={{ minHeight: 36 }}
        >
          {GRANULARITY_OPTIONS.map((option) => (
            <Tab key={option.value} value={option.value} label={option.label} sx={{ minHeight: 36, py: 0.5 }} />
          ))}
        </Tabs>
      </FilterToolbar>

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
            onAssign={(projectId, designerId) => {
              if (!designerId) return;
              void requestAssign(projectId, designerId);
            }}
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

      <FilterDrawer
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title="Planning filters"
        onApply={applyFilters}
        onReset={resetFilters}
      >
        <Box sx={compactFilterFieldSx}>
          <FormSelect
            label="Team"
            size="small"
            value={draftTeamFilter}
            options={[
              { value: 'all', label: 'All Teams' },
              ...(teamsQuery.data ?? []).map((team) => ({ value: team.id, label: team.name })),
            ]}
            onChange={(event) => setDraftTeamFilter(String(event.target.value))}
          />
        </Box>
        <FilterGroup title="Planning" icon={<CalendarMonthOutlinedIcon sx={{ fontSize: 14 }} />}>
          <Box sx={compactFilterFieldSx}>
            <FormSelect
              label="Time scale"
              size="small"
              value={draftGranularity}
              options={GRANULARITY_OPTIONS.map((option) => ({
                value: option.value,
                label: option.label,
              }))}
              onChange={(event) =>
                setDraftGranularity(event.target.value as ResourcePlanningGranularity)
              }
            />
          </Box>
        </FilterGroup>
      </FilterDrawer>

      <ConfirmDialog
        open={Boolean(pendingAssign)}
        title="Skill fit warning"
        message={pendingAssign?.message ?? ''}
        confirmLabel="Assign anyway"
        danger
        loading={assignMutation.isPending}
        onClose={() => setPendingAssign(null)}
        onConfirm={() => {
          if (!pendingAssign) return;
          assignMutation.mutate({
            project_id: pendingAssign.project_id,
            designer_id: pendingAssign.designer_id,
          });
        }}
      />
    </PageContainer>
  );
}
