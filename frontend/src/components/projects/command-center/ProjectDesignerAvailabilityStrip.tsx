import { Chip, Stack, Typography } from '@mui/material';
import type {
  DashboardDesignerAvailabilityRow,
  DashboardDesignerAvailabilitySummary,
} from '../../../types';

interface ProjectDesignerAvailabilityStripProps {
  summary: DashboardDesignerAvailabilitySummary;
  designers: DashboardDesignerAvailabilityRow[];
  selectedDesignerId?: string;
  onSelect: (designerId: string | undefined) => void;
}

const STATUS_LABELS = {
  available: 'Available',
  working: 'Busy',
  on_hold: 'On Hold',
  leave: 'On Leave',
} as const;

export function ProjectDesignerAvailabilityStrip({
  summary,
  designers,
  selectedDesignerId,
  onSelect,
}: ProjectDesignerAvailabilityStripProps) {
  const summaryChips = [
    { label: `Available (${summary.available})`, status: 'available' as const },
    { label: `Busy (${summary.allocated})`, status: 'working' as const },
    { label: `On Leave (${summary.on_leave})`, status: 'leave' as const },
  ];

  const overloaded = designers.filter(
    (designer) => designer.status === 'working' && designer.current_tool_number,
  ).length;

  return (
    <Stack spacing={1} sx={{ mb: 2.5 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, letterSpacing: '0.04em' }}>
        DESIGNER AVAILABILITY
      </Typography>
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
        {summaryChips.map((chip) => (
          <Chip key={chip.label} label={chip.label} variant="outlined" size="small" />
        ))}
        {overloaded > 0 ? (
          <Chip label={`Overloaded (${overloaded})`} color="warning" variant="outlined" size="small" />
        ) : null}
      </Stack>
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
        {designers.slice(0, 10).map((designer) => (
          <Chip
            key={designer.user_id}
            label={`${designer.designer_name} · ${STATUS_LABELS[designer.status]}`}
            variant={selectedDesignerId === designer.user_id ? 'filled' : 'outlined'}
            color={
              designer.status === 'available'
                ? 'success'
                : designer.status === 'working'
                  ? 'info'
                  : 'default'
            }
            onClick={() =>
              onSelect(
                selectedDesignerId === designer.user_id ? undefined : designer.user_id,
              )
            }
            size="small"
            sx={{ fontWeight: 600 }}
          />
        ))}
      </Stack>
    </Stack>
  );
}
