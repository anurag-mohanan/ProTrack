import { Stack, Chip } from '@mui/material';
import type { ProjectClassificationFilter } from '../../../utils/projectCommandCenter';

interface ProjectClassificationFilterStripProps {
  counts: {
    fullDesign: number;
    smallTask: number;
    unclassified: number;
  };
  activeClassification: ProjectClassificationFilter;
  onSelect: (classification: ProjectClassificationFilter) => void;
  showUnclassifiedReview?: boolean;
}

export function ProjectClassificationFilterStrip({
  counts,
  activeClassification,
  onSelect,
  showUnclassifiedReview = false,
}: ProjectClassificationFilterStripProps) {
  const chips: Array<{
    key: ProjectClassificationFilter;
    label: string;
    color?: 'default' | 'primary' | 'warning';
    visible: boolean;
  }> = [
    {
      key: 'full_design',
      label: `Full Design (${counts.fullDesign})`,
      color: 'primary',
      visible: counts.fullDesign > 0 || activeClassification === 'full_design',
    },
    {
      key: 'small_task',
      label: `Small Tasks (${counts.smallTask})`,
      color: 'default',
      visible: counts.smallTask > 0 || activeClassification === 'small_task',
    },
    {
      key: 'unclassified',
      label: `Needs Classification (${counts.unclassified})`,
      color: 'warning',
      visible:
        showUnclassifiedReview &&
        (counts.unclassified > 0 || activeClassification === 'unclassified'),
    },
  ];

  const visibleChips = chips.filter((chip) => chip.visible);
  if (!visibleChips.length) return null;

  return (
    <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
      {visibleChips.map((chip) => (
        <Chip
          key={chip.key}
          label={chip.label}
          size="small"
          color={chip.color}
          variant={activeClassification === chip.key ? 'filled' : 'outlined'}
          onClick={() => onSelect(activeClassification === chip.key ? 'all' : chip.key)}
          sx={{ fontWeight: 600, height: 24, '& .MuiChip-label': { px: 1 } }}
        />
      ))}
    </Stack>
  );
}
