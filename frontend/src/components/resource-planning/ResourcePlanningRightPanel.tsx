import { useMemo } from 'react';
import { Box, Chip, Divider, Stack, Typography } from '@mui/material';
import type {
  ResourceAllocationBlock,
  ResourcePlanningDesignerRow,
  ResourcePlanningGrid,
  UnassignedProjectBlock,
} from '../../types/ResourcePlanning';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { HealthIndicator, ProgressRing, UtilizationBar } from '../ui/design-system';
import { designTokens } from '../../theme/designTokens';
import { formatCellValue, formatNumber } from '../../utils/format';

interface CustomerAllocation {
  customer_name: string;
  active_tools: number;
  assigned_designers: Set<string>;
  total_hours: number;
  utilization: number;
}

interface ResourcePlanningRightPanelProps {
  grid: ResourcePlanningGrid;
  selectedDesignerId: string | null;
  selectedProjectId: string | null;
  onSelectProject: (projectId: string | null) => void;
}

function collectCustomerAllocations(grid: ResourcePlanningGrid): CustomerAllocation[] {
  const map = new Map<string, CustomerAllocation>();

  const addBlock = (block: ResourceAllocationBlock, designerName?: string) => {
    const key = block.customer_name;
    const existing = map.get(key) ?? {
      customer_name: key,
      active_tools: 0,
      assigned_designers: new Set<string>(),
      total_hours: 0,
      utilization: 0,
    };
    existing.active_tools += 1;
    existing.total_hours += block.hours;
    if (designerName) existing.assigned_designers.add(designerName);
    map.set(key, existing);
  };

  grid.designers.forEach((designer) => {
    designer.cells.forEach((cell) => {
      cell.blocks.forEach((block) => addBlock(block, designer.designer_name));
    });
  });
  grid.unassigned_projects.forEach((project) => {
    const key = project.customer_name;
    const existing = map.get(key) ?? {
      customer_name: key,
      active_tools: 0,
      assigned_designers: new Set<string>(),
      total_hours: 0,
      utilization: 0,
    };
    existing.active_tools += 1;
    existing.total_hours += project.remaining_hours;
    map.set(key, existing);
  });

  const maxHours = Math.max(...[...map.values()].map((c) => c.total_hours), 1);
  return [...map.values()]
    .map((c) => ({
      ...c,
      utilization: Math.round((c.total_hours / maxHours) * 100),
      assigned_designers: c.assigned_designers,
    }))
    .sort((a, b) => b.total_hours - a.total_hours);
}

function findProject(
  grid: ResourcePlanningGrid,
  projectId: string | null,
): { project: UnassignedProjectBlock | null; blocks: ResourceAllocationBlock[]; designer: ResourcePlanningDesignerRow | null } {
  if (!projectId) return { project: null, blocks: [], designer: null };

  const unassigned = grid.unassigned_projects.find((p) => p.project_id === projectId) ?? null;
  const blocks: ResourceAllocationBlock[] = [];
  let designer: ResourcePlanningDesignerRow | null = null;

  grid.designers.forEach((d) => {
    d.cells.forEach((cell) => {
      cell.blocks.forEach((block) => {
        if (block.project_id === projectId) {
          blocks.push(block);
          designer = d;
        }
      });
    });
  });

  return { project: unassigned, blocks, designer };
}

export function ResourcePlanningRightPanel({
  grid,
  selectedDesignerId,
  selectedProjectId,
  onSelectProject,
}: ResourcePlanningRightPanelProps) {
  const customers = useMemo(() => collectCustomerAllocations(grid), [grid]);
  const selectedDesigner = grid.designers.find((d) => d.user_id === selectedDesignerId) ?? null;
  const projectDetail = useMemo(
    () => findProject(grid, selectedProjectId),
    [grid, selectedProjectId],
  );

  const designerUtil =
    selectedDesigner && selectedDesigner.capacity_hours > 0
      ? Math.round((selectedDesigner.allocated_hours / selectedDesigner.capacity_hours) * 100)
      : 0;

  return (
    <Stack spacing={2} sx={{ height: '100%', overflow: 'auto' }}>
      {selectedDesigner ? (
        <DashboardPanel title="Designer Capacity" subtitle={selectedDesigner.designer_name}>
          <Stack spacing={1.5}>
            <Box sx={{ display: 'flex', justifyContent: 'center' }}>
              <ProgressRing value={designerUtil} label="Utilization" size={96} />
            </Box>
            <UtilizationBar label="Load" value={designerUtil} />
            <Typography variant="body2">
              Allocated: <strong>{formatNumber(selectedDesigner.allocated_hours)}h</strong>
            </Typography>
            <Typography variant="body2">
              Capacity: <strong>{formatNumber(selectedDesigner.capacity_hours)}h</strong>
            </Typography>
            <Typography variant="body2">
              Remaining: <strong>{formatNumber(selectedDesigner.remaining_hours)}h</strong>
            </Typography>
            <Chip
              size="small"
              label={selectedDesigner.availability_status}
              sx={{
                alignSelf: 'flex-start',
                bgcolor: selectedDesigner.availability_status.toLowerCase().includes('leave')
                  ? designTokens.semantic.neutralSoft
                  : designTokens.semantic.primarySoft,
              }}
            />
          </Stack>
        </DashboardPanel>
      ) : null}

      {projectDetail.project || projectDetail.blocks.length ? (
        <DashboardPanel
          title="Project Details"
          subtitle={
            projectDetail.project?.tool_number ??
            projectDetail.blocks[0]?.tool_number ??
            'Selected assignment'
          }
        >
          <Stack spacing={1}>
            <Typography variant="body2">
              Customer:{' '}
              <strong>
                {projectDetail.project?.customer_name ?? projectDetail.blocks[0]?.customer_name}
              </strong>
            </Typography>
            {projectDetail.designer ? (
              <Typography variant="body2">
                Designer: <strong>{projectDetail.designer.designer_name}</strong>
              </Typography>
            ) : (
              <Chip label="Unassigned" size="small" color="warning" sx={{ alignSelf: 'flex-start' }} />
            )}
            {projectDetail.project ? (
              <>
                <Typography variant="body2">
                  Quoted: <strong>{formatNumber(projectDetail.project.quoted_hours)}h</strong>
                </Typography>
                <Typography variant="body2">
                  Remaining: <strong>{formatNumber(projectDetail.project.remaining_hours)}h</strong>
                </Typography>
                <Typography variant="body2">
                  Due: <strong>{projectDetail.project.due_date}</strong>
                </Typography>
              </>
            ) : null}
            {projectDetail.blocks.map((block) => (
              <Box key={`${block.project_id}-${block.milestone_name}`} sx={{ pt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  {formatCellValue(block.milestone_name)} · {formatNumber(block.hours)}h
                </Typography>
              </Box>
            ))}
            <Chip
              size="small"
              label="Clear selection"
              onClick={() => onSelectProject(null)}
              sx={{ alignSelf: 'flex-start', mt: 0.5 }}
            />
          </Stack>
        </DashboardPanel>
      ) : null}

      <DashboardPanel title="Utilization" subtitle="Team capacity overview">
        <Stack spacing={1.25}>
          {grid.team_summary.slice(0, 5).map((team) => (
            <Box key={team.team_id}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {team.team_name}
                </Typography>
                <Typography variant="caption">{formatNumber(team.utilization_percent)}%</Typography>
              </Box>
              <UtilizationBar label="" value={team.utilization_percent} />
            </Box>
          ))}
        </Stack>
      </DashboardPanel>

      <DashboardPanel title="Customer Allocation" subtitle="Active workload by customer">
        <Stack spacing={1.5} divider={<Divider flexItem />}>
          {customers.slice(0, 6).map((customer) => (
            <Box
              key={customer.customer_name}
              sx={{
                p: 1.25,
                borderRadius: `${designTokens.radius.md}px`,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: designTokens.semantic.background,
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                {customer.customer_name}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                {customer.active_tools} tools · {customer.assigned_designers.size} designers ·{' '}
                {formatNumber(customer.total_hours)}h
              </Typography>
              <UtilizationBar label="" value={customer.utilization} />
            </Box>
          ))}
          {!customers.length ? (
            <Typography variant="body2" color="text.secondary">
              No customer allocations in this horizon.
            </Typography>
          ) : null}
        </Stack>
      </DashboardPanel>

      <DashboardPanel title="Capacity Legend">
        <Stack spacing={0.75}>
          {(
            [
              ['green', 'Available', designTokens.utilization.low],
              ['orange', 'Near capacity', designTokens.utilization.medium],
              ['red', 'Overloaded', designTokens.utilization.high],
              ['grey', 'Leave / unavailable', designTokens.semantic.neutral],
            ] as const
          ).map(([key, label, color]) => (
            <Box key={key} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <HealthIndicator health={key === 'green' ? 'green' : key === 'orange' ? 'yellow' : key === 'red' ? 'red' : 'grey'} />
              <Typography variant="caption">{label}</Typography>
              <Box sx={{ flex: 1, height: 4, borderRadius: 2, bgcolor: color, maxWidth: 48, ml: 'auto' }} />
            </Box>
          ))}
        </Stack>
      </DashboardPanel>
    </Stack>
  );
}
