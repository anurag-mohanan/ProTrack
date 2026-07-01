import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ADMIN_SETTINGS_ITEMS } from '../../config/adminNavigation';
import SystemSettingsPage from './SystemSettingsPage';

export default function AdminSettingsHubPage() {
  return (
    <Box>
      <PageHeader
        title="Settings"
        subtitle="Application, company, and notification configuration"
      />

      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {ADMIN_SETTINGS_ITEMS.map((item) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={item.id}>
            <AdminActionCard {...item} />
          </Grid>
        ))}
      </Grid>

      <SystemSettingsPage embedded />
    </Box>
  );
}
