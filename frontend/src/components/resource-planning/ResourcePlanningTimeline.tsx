import { useMemo } from 'react';
import { Box, Chip, Tooltip, Typography, useTheme } from '@mui/material';
import type {
  ResourcePlanningGrid,
  ResourceStatusColor,
} from '../../types/ResourcePlanning';
import { designTokens } from '../../theme/designTokens';
import { formatNumber, toFiniteNumber } from '../../utils/format';

const COLOR_MAP: Record<ResourceStatusColor, string> = {
  green: designTokens.utilization.low,
  blue: designTokens.semantic.primary,
  orange: designTokens.utilization.medium,
  red: designTokens.utilization.high,
  grey: designTokens.semantic.neutral,
};

const DRAG_PROJECT = 'application/x-protrack-project';

interface ResourcePlanningTimelineProps {
  grid: ResourcePlanningGrid;
  selectedDesignerId: string | null;
  selectedProjectId: string | null;
  onAssign: (projectId: string, designerId: string | null) => void;
  onSelectProject: (projectId: string) => void;
}

export function ResourcePlanningTimeline({
  grid,
  selectedDesignerId,
  selectedProjectId,
  onAssign,
  onSelectProject,
}: ResourcePlanningTimelineProps) {
  const theme = useTheme();

  const filteredDesigners = useMemo(() => {
    if (!selectedDesignerId) return grid.designers;
    return grid.designers.filter((d) => d.user_id === selectedDesignerId);
  }, [grid.designers, selectedDesignerId]);

  const cellMap = useMemo(() => {
    const map = new Map<string, Map<string, (typeof grid.designers)[0]['cells'][number]>>();
    grid.designers.forEach((designer) => {
      map.set(designer.user_id, new Map(designer.cells.map((cell) => [cell.period_key, cell])));
    });
    return map;
  }, [grid.designers]);

  const periodWidth = Math.max(120, Math.min(180, 720 / Math.max(grid.periods.length, 1)));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <Box
        sx={{
          p: 1.5,
          mb: 1,
          borderRadius: `${designTokens.radius.md}px`,
          border: '1px dashed',
          borderColor: 'divider',
          bgcolor: designTokens.semantic.background,
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const projectId = e.dataTransfer.getData(DRAG_PROJECT);
          if (projectId) onAssign(projectId, null);
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 700, display: 'block', mb: 0.75 }}>
          Unassigned — drag to timeline
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          {grid.unassigned_projects.length ? (
            grid.unassigned_projects.map((project) => (
              <Chip
                key={project.project_id}
                draggable
                size="small"
                label={`${project.tool_number} · ${project.customer_name}`}
                onClick={() => onSelectProject(project.project_id)}
                onDragStart={(e) => {
                  e.dataTransfer.setData(DRAG_PROJECT, project.project_id);
                  e.dataTransfer.effectAllowed = 'move';
                }}
                color={selectedProjectId === project.project_id ? 'primary' : 'default'}
                sx={{ cursor: 'grab' }}
              />
            ))
          ) : (
            <Typography variant="body2" color="text.secondary">
              All projects assigned.
            </Typography>
          )}
        </Box>
      </Box>

      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: `${designTokens.radius.lg}px`,
          bgcolor: designTokens.semantic.card,
        }}
      >
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: `200px repeat(${grid.periods.length}, ${periodWidth}px)`,
            minWidth: 200 + grid.periods.length * periodWidth,
            position: 'sticky',
            top: 0,
            zIndex: 2,
            bgcolor: designTokens.semantic.card,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Box sx={{ p: 1.5, fontWeight: 700, fontSize: '0.75rem' }}>Designer / Period</Box>
          {grid.periods.map((period) => (
            <Box key={period.key} sx={{ p: 1.5, textAlign: 'center', borderLeft: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>
                {period.label}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
                {period.start_date}
              </Typography>
            </Box>
          ))}
        </Box>

        {filteredDesigners.map((designer) => (
          <Box
            key={designer.user_id}
            sx={{
              display: 'grid',
              gridTemplateColumns: `200px repeat(${grid.periods.length}, ${periodWidth}px)`,
              minWidth: 200 + grid.periods.length * periodWidth,
              borderBottom: '1px solid',
              borderColor: 'divider',
              '&:hover': { bgcolor: theme.palette.action.hover },
            }}
          >
            <Box
              sx={{
                p: 1.5,
                position: 'sticky',
                left: 0,
                zIndex: 1,
                bgcolor: designTokens.semantic.card,
                borderRight: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {designer.designer_name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {formatNumber(designer.allocated_hours)} / {formatNumber(designer.capacity_hours)}h
              </Typography>
            </Box>
            {grid.periods.map((period) => {
              const cell = cellMap.get(designer.user_id)?.get(period.key);
              if (!cell) return <Box key={period.key} />;
              const capacity = toFiniteNumber(cell.capacity_hours);
              const allocated = toFiniteNumber(cell.allocated_hours);
              const remaining = toFiniteNumber(cell.remaining_hours);
              const util =
                capacity > 0 ? Math.round((allocated / capacity) * 100) : allocated > 0 ? 100 : 0;
              return (
                <Box
                  key={period.key}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'move';
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const projectId = e.dataTransfer.getData(DRAG_PROJECT);
                    if (projectId) onAssign(projectId, designer.user_id);
                  }}
                  sx={{
                    p: 0.75,
                    minHeight: 72,
                    borderLeft: `3px solid ${COLOR_MAP[cell.status_color]}`,
                    bgcolor: `${COLOR_MAP[cell.status_color]}12`,
                  }}
                >
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    {util}% · {formatNumber(remaining, 1) || '0'}h free
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    {cell.blocks.map((block) => (
                      <Tooltip
                        key={`${block.project_id}-${period.key}`}
                        title={`${block.customer_name} · ${block.milestone_name ?? 'Milestone'} · ${formatNumber(block.hours)}h`}
                      >
                        <Box
                          draggable
                          onClick={() => onSelectProject(block.project_id)}
                          onDragStart={(e) => {
                            e.dataTransfer.setData(DRAG_PROJECT, block.project_id);
                            e.dataTransfer.effectAllowed = 'move';
                          }}
                          sx={{
                            px: 0.75,
                            py: 0.35,
                            borderRadius: `${designTokens.radius.sm}px`,
                            bgcolor: COLOR_MAP[block.status_color],
                            color: '#fff',
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            cursor: 'grab',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            outline: selectedProjectId === block.project_id ? '2px solid' : undefined,
                            outlineColor: 'primary.main',
                            outlineOffset: 1,
                          }}
                        >
                          {block.tool_number} ({formatNumber(block.hours)}h)
                        </Box>
                      </Tooltip>
                    ))}
                  </Box>
                </Box>
              );
            })}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
