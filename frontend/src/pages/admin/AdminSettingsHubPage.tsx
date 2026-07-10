import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { getAdminSettingsItems } from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';
import { accessContextFromUser } from '../../utils/permissions';

export default function AdminSettingsHubPage() {
  const { user } = useAuth();
  const items = getAdminSettingsItems(accessContextFromUser(user));
  return (
    <Box>
      <PageHeader
        title="Settings"
        subtitle="Company profile, holidays, departments, paths, and notifications"
      />

      <Grid container spacing={2.5}>
        {items.map((item) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={item.id}>
            <AdminActionCard {...item} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
