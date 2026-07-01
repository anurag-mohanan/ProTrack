import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ADMIN_REPORT_ITEMS } from '../../config/adminNavigation';

export default function AdminReportsPage() {
  return (
    <Box>
      <PageHeader
        title="Administration Reports"
        subtitle="Audit, activity, and import reporting for administrators"
      />

      <Grid container spacing={2.5}>
        {ADMIN_REPORT_ITEMS.map((item) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={item.id}>
            <AdminActionCard {...item} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
