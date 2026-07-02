import { Box, Grid, Typography } from '@mui/material';
import type { AdminCreateAction, AdminHubItem } from '../../config/adminNavigation';
import { AdminActionCard } from './AdminActionCard';

type AdminCardItem = AdminHubItem | AdminCreateAction;

interface AdminSectionCardsProps {
  title: string;
  description?: string;
  items: AdminCardItem[];
  compact?: boolean;
}

export function AdminSectionCards({ title, description, items, compact = false }: AdminSectionCardsProps) {
  return (
    <Box sx={{ mb: compact ? 2.5 : 3.5 }}>
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
        {title}
      </Typography>
      {description ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {description}
        </Typography>
      ) : (
        <Box sx={{ mb: 2 }} />
      )}
      <Grid container spacing={2}>
        {items.map((item) => (
          <Grid key={item.id} size={{ xs: 12, sm: 6, md: 4, lg: compact ? 3 : 4 }}>
            <AdminActionCard
              title={item.title}
              description={item.description}
              icon={item.icon}
              path={item.path}
              comingSoon={'comingSoon' in item ? item.comingSoon : false}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
