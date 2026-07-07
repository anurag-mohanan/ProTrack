import { Box, Stack } from '@mui/material';
import type { DashboardDesignerAvailabilityRow } from '../../types';
import { UtilizationBar } from '../ui/design-system/UtilizationBar';

function utilizationFromStatus(row: DashboardDesignerAvailabilityRow): number {
  switch (row.status) {
    case 'working':
      return 92;
    case 'on_hold':
      return 68;
    case 'leave':
      return 0;
    case 'available':
    default:
      return row.current_tool_number ? 55 : 28;
  }
}

interface DesignerUtilizationListProps {
  rows: DashboardDesignerAvailabilityRow[];
  limit?: number;
}

export function DesignerUtilizationList({ rows, limit = 6 }: DesignerUtilizationListProps) {
  if (!rows.length) {
    return null;
  }

  return (
    <Stack spacing={1.75}>
      {rows.slice(0, limit).map((row) => (
        <Box key={row.user_id}>
          <UtilizationBar
            label={row.designer_name}
            value={utilizationFromStatus(row)}
          />
        </Box>
      ))}
    </Stack>
  );
}
