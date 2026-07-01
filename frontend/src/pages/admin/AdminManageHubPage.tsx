import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminSearchBar } from '../../components/admin/AdminSearchBar';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ContentCard } from '../../components/ui/cards';
import { ADMIN_MANAGE_ITEMS } from '../../config/adminNavigation';

export default function AdminManageHubPage() {
  return (
    <Box>
      <PageHeader
        title="Manage"
        subtitle="Master data — search, create, edit, archive, and delete"
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard title="Search master data">
          <AdminSearchBar placeholder="Search users, customers, teams, roles…" />
        </ContentCard>
      </Box>

      <Grid container spacing={2.5}>
        {ADMIN_MANAGE_ITEMS.map((item) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={item.id}>
            <AdminActionCard {...item} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
