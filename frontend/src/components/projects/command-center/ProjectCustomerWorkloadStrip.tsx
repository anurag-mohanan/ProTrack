import { Chip, Stack, Typography } from '@mui/material';
import type { DashboardCustomerWorkloadRow } from '../../../types';

interface ProjectCustomerWorkloadStripProps {
  rows: DashboardCustomerWorkloadRow[];
  selectedCustomerId?: string;
  onSelect: (customerId: string | undefined) => void;
}

export function ProjectCustomerWorkloadStrip({
  rows,
  selectedCustomerId,
  onSelect,
}: ProjectCustomerWorkloadStripProps) {
  if (!rows.length) return null;

  return (
    <Stack spacing={1} sx={{ mb: 2 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, letterSpacing: '0.04em' }}>
        CUSTOMER WORKLOAD
      </Typography>
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
        {rows.slice(0, 8).map((row) => (
          <Chip
            key={row.customer_id}
            label={`${row.customer_name} · ${row.active_tools} Active`}
            variant={selectedCustomerId === row.customer_id ? 'filled' : 'outlined'}
            color="primary"
            onClick={() =>
              onSelect(selectedCustomerId === row.customer_id ? undefined : row.customer_id)
            }
            sx={{ fontWeight: 600 }}
          />
        ))}
      </Stack>
    </Stack>
  );
}
