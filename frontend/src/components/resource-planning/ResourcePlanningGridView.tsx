import { useMemo } from 'react';
import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import type {
  ResourcePlanningDesignerRow,
  ResourcePlanningGrid,
  ResourceStatusColor,
  UnassignedProjectBlock,
} from '../../types/ResourcePlanning';
import { formatNumber } from '../../utils/format';

const COLOR_MAP: Record<ResourceStatusColor, string> = {
  green: 'success.main',
  blue: 'info.main',
  orange: 'warning.main',
  red: 'error.main',
  grey: 'text.disabled',
};

const DRAG_PROJECT = 'application/x-protrack-project';

interface ResourcePlanningGridViewProps {
  grid: ResourcePlanningGrid;
  onAssign: (projectId: string, designerId: string | null) => void;
}

function DraggableProjectChip({
  project,
}: {
  project: Pick<UnassignedProjectBlock, 'project_id' | 'tool_number' | 'customer_name'>;
}) {
  return (
    <Chip
      draggable
      size="small"
      label={`${project.tool_number} · ${project.customer_name}`}
      onDragStart={(event) => {
        event.dataTransfer.setData(DRAG_PROJECT, project.project_id);
        event.dataTransfer.effectAllowed = 'move';
      }}
      sx={{ cursor: 'grab', mb: 0.5, mr: 0.5 }}
    />
  );
}

function DesignerCell({
  cell,
  designerId,
  onAssign,
}: {
  cell: ResourcePlanningDesignerRow['cells'][number];
  designerId: string;
  onAssign: (projectId: string, designerId: string | null) => void;
}) {
  const theme = useTheme();
  const borderColor = theme.palette.mode === 'dark' ? 'divider' : COLOR_MAP[cell.status_color];

  return (
    <TableCell
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
      }}
      onDrop={(event) => {
        event.preventDefault();
        const projectId = event.dataTransfer.getData(DRAG_PROJECT);
        if (projectId) onAssign(projectId, designerId);
      }}
      sx={{
        verticalAlign: 'top',
        minWidth: 140,
        borderLeft: `3px solid ${borderColor}`,
        bgcolor: `${borderColor}10`,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        Cap {formatNumber(cell.capacity_hours)} · Alloc {formatNumber(cell.allocated_hours)}
      </Typography>
      <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}>
        Rem {formatNumber(cell.remaining_hours)}h
      </Typography>
      {cell.blocks.map((block) => (
        <Tooltip
          key={`${block.project_id}-${cell.period_key}`}
          title={`${block.customer_name} · ${block.milestone_name ?? 'No milestone'} · ${formatNumber(block.hours)}h`}
        >
          <Chip
            draggable
            size="small"
            label={block.tool_number}
            onDragStart={(event) => {
              event.dataTransfer.setData(DRAG_PROJECT, block.project_id);
              event.dataTransfer.effectAllowed = 'move';
            }}
            sx={{
              mb: 0.5,
              mr: 0.5,
              cursor: 'grab',
              bgcolor: `${COLOR_MAP[block.status_color as ResourceStatusColor]}22`,
              borderColor: COLOR_MAP[block.status_color as ResourceStatusColor],
              borderWidth: 1,
              borderStyle: 'solid',
            }}
          />
        </Tooltip>
      ))}
    </TableCell>
  );
}

export function ResourcePlanningGridView({ grid, onAssign }: ResourcePlanningGridViewProps) {
  const cellMap = useMemo(() => {
    const map = new Map<string, Map<string, ResourcePlanningDesignerRow['cells'][number]>>();
    grid.designers.forEach((designer) => {
      const periodMap = new Map(designer.cells.map((cell) => [cell.period_key, cell]));
      map.set(designer.user_id, periodMap);
    });
    return map;
  }, [grid.designers]);

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Unassigned projects — drag onto a designer cell to assign
        </Typography>
        <Box
          onDragOver={(event) => {
            event.preventDefault();
          }}
          onDrop={(event) => {
            event.preventDefault();
            const projectId = event.dataTransfer.getData(DRAG_PROJECT);
            if (projectId) onAssign(projectId, null);
          }}
          sx={{ minHeight: 40 }}
        >
          {grid.unassigned_projects.length ? (
            grid.unassigned_projects.map((project) => (
              <DraggableProjectChip key={project.project_id} project={project} />
            ))
          ) : (
            <Typography variant="body2" color="text.secondary">
              All active projects have a designer assigned.
            </Typography>
          )}
        </Box>
      </Paper>

      <Paper sx={{ overflow: 'auto' }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ minWidth: 200, position: 'sticky', left: 0, zIndex: 3, bgcolor: 'background.paper' }}>
                Designer
              </TableCell>
              <TableCell sx={{ minWidth: 120 }}>Capacity</TableCell>
              {grid.periods.map((period) => (
                <TableCell key={period.key} sx={{ minWidth: 140 }}>
                  {period.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {grid.designers.map((designer) => (
              <TableRow key={designer.user_id} hover>
                <TableCell sx={{ position: 'sticky', left: 0, bgcolor: 'background.paper', zIndex: 2 }}>
                  <Typography sx={{ fontWeight: 600 }}>{designer.designer_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {designer.team_name ?? '—'} · {designer.availability_status}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    {formatNumber(designer.allocated_hours)} / {formatNumber(designer.capacity_hours)}h
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Rem {formatNumber(designer.remaining_hours)}h
                  </Typography>
                </TableCell>
                {grid.periods.map((period) => {
                  const cell = cellMap.get(designer.user_id)?.get(period.key);
                  if (!cell) return <TableCell key={period.key} />;
                  return (
                    <DesignerCell
                      key={period.key}
                      cell={cell}
                      designerId={designer.user_id}
                      onAssign={onAssign}
                    />
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
