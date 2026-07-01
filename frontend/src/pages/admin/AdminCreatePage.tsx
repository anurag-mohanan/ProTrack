import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ADMIN_CREATE_ACTIONS } from '../../config/adminNavigation';

export default function AdminCreatePage() {
  return (
    <Box>
      <PageHeader
        title="Create"
        subtitle="Quick actions to add new records across the system"
      />

      <Grid container spacing={2.5}>
        {ADMIN_CREATE_ACTIONS.map((action) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={action.id}>
            <AdminActionCard {...action} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
