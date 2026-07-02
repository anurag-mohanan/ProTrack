import { Box, Grid, Typography } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ContentCard } from '../../components/ui/cards';
import { ADMIN_SYSTEM_ITEMS } from '../../config/adminNavigation';
import {
  PRODUCT_NAME,
  RELEASE_LABEL,
  VERSION_DISPLAY,
} from '../../config/appMeta';

export default function AdminSystemPage() {
  return (
    <Box>
      <PageHeader
        title="System Health"
        subtitle="Release information and platform maintenance tools"
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard title="Release Information">
          <Typography variant="body1" sx={{ fontWeight: 700, mb: 0.5 }}>
            {PRODUCT_NAME} {VERSION_DISPLAY}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {RELEASE_LABEL}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Frontend and API are configured for deployment at protrack.prosohm.com.
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
