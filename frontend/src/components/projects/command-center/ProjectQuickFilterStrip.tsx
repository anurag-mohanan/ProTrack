import { Stack, Chip } from '@mui/material';
import type { ProjectQuickFilter } from '../../../utils/projectCommandCenter';

interface QuickFilterChip {
  key: ProjectQuickFilter;
  label: string;
  color?: 'success' | 'warning' | 'error' | 'default' | 'primary';
}

interface ProjectQuickFilterStripProps {
  counts: {
    inProgress: number;
    onHold: number;
    overdue: number;
    dueWeek: number;
    notStarted: number;
  };
  activeFilter: ProjectQuickFilter;
  onSelect: (filter: ProjectQuickFilter) => void;
}

export function ProjectQuickFilterStrip({
  counts,
  activeFilter,
  onSelect,
}: ProjectQuickFilterStripProps) {
  const chips: QuickFilterChip[] = [
    { key: 'in_progress', label: `In Progress (${counts.inProgress})`, color: 'success' },
    { key: 'on_hold', label: `On Hold (${counts.onHold})`, color: 'warning' },
    { key: 'overdue', label: `Overdue (${counts.overdue})`, color: 'error' },
    { key: 'due_week', label: `Due This Week (${counts.dueWeek})`, color: 'primary' },
    { key: 'not_started', label: `Not Started (${counts.notStarted})`, color: 'default' },
  ];

  return (
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.75, mb: 1.75 }}>
      {chips.map((chip) => (
        <Chip
          key={chip.key}
          label={chip.label}
          size="small"
          color={chip.color}
          variant={activeFilter === chip.key ? 'filled' : 'outlined'}
          onClick={() => onSelect(activeFilter === chip.key ? 'none' : chip.key)}
          sx={{ fontWeight: 600, height: 28 }}
        />
      ))}
    </Stack>
  );
}
