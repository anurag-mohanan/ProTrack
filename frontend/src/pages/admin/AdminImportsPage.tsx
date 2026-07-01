import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ADMIN_IMPORT_ITEMS } from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';

export default function AdminImportsPage() {
  const { user } = useAuth();
  const items = ADMIN_IMPORT_ITEMS(user?.role_name ?? '');

  return (
    <Box>
      <PageHeader
        title="Imports"
        subtitle="Historical data import, logs, and future bulk import tools"
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
