import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { getAdminCreateActions } from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';
import { accessContextFromUser } from '../../utils/permissions';

export default function AdminCreatePage() {
  const { user } = useAuth();
  const actions = getAdminCreateActions(accessContextFromUser(user));

  return (
    <Box>
      <PageHeader
        title="Create"
        subtitle="Quick actions to add new records across the system"
      />

      <Grid container spacing={2.5}>
        {actions.map((action) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={action.id}>
            <AdminActionCard {...action} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
