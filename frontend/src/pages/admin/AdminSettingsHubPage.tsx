import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ADMIN_SETTINGS_ITEMS } from '../../config/adminNavigation';

export default function AdminSettingsHubPage() {
  return (
    <Box>
      <PageHeader
        title="Settings"
        subtitle="Company profile, holidays, departments, paths, and notifications"
      />

      <Grid container spacing={2.5}>
        {ADMIN_SETTINGS_ITEMS.map((item) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={item.id}>
            <AdminActionCard {...item} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
