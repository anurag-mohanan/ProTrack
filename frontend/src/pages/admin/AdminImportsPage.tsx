import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ADMIN_IMPORT_ALL_ITEMS } from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';
import { accessContextFromUser } from '../../utils/permissions';

export default function AdminImportsPage() {
  const { user } = useAuth();
  const items = ADMIN_IMPORT_ALL_ITEMS(accessContextFromUser(user));

  return (
    <Box>
      <PageHeader
        title="Import"
        subtitle="History packs (employment, finance, customers), legacy project/timesheet importers, and bulk tools"
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
