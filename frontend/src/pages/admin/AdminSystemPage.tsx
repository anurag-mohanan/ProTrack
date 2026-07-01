import { Box, Grid, Typography } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ContentCard } from '../../components/ui/cards';
import { ADMIN_SYSTEM_ITEMS } from '../../config/adminNavigation';

const APP_VERSION = '1.0.0';

export default function AdminSystemPage() {
  return (
    <Box>
      <PageHeader
        title="System"
        subtitle="Developer and system administration tools (Admin only)"
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard title="Version Information">
          <Typography variant="body2" color="text.secondary">
            ProTrack {APP_VERSION} · Backend API connected
          </Typography>
        </ContentCard>
      </Box>

      <Grid container spacing={2.5}>
        {ADMIN_SYSTEM_ITEMS.map((item) => (
          <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={item.id}>
            <AdminActionCard
              {...item}
              comingSoon={item.id !== 'version' ? item.comingSoon : false}
              path={item.id === 'version' ? '/admin/system' : item.path}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
