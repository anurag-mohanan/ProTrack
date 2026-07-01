import { Box, Grid } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminSearchBar } from '../../components/admin/AdminSearchBar';
import { AdminActionCard } from '../../components/admin/AdminActionCard';
import { ContentCard } from '../../components/ui/cards';
import {
  ADMIN_CREATE_ACTIONS,
  ADMIN_IMPORT_ITEMS,
  ADMIN_MANAGE_ITEMS,
  getAdminNavSections,
} from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const roleName = user?.role_name ?? '';
  const sections = getAdminNavSections(roleName);

  return (
    <Box>
      <PageHeader
        title="Administration"
        subtitle="Central hub for configuration, master data, and imports"
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard title="Global search">
          <AdminSearchBar />
        </ContentCard>
      </Box>

      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {sections.slice(0, 6).map((section) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={section.id}>
            <AdminActionCard
              title={section.label}
              description={
                section.children
                  ? `${section.children.length} areas`
                  : `Open ${section.label.toLowerCase()}`
              }
              icon={section.icon}
              path={section.path ?? `/admin/${section.id}`}
            />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2.5}>
        <Grid size={{ xs: 12, md: 4 }}>
          <AdminActionCard
            title="Quick Create"
            description="Add users, customers, teams, and more."
            icon={ADMIN_CREATE_ACTIONS[0].icon}
            path="/admin/create"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <AdminActionCard
            title="Manage Data"
            description={`${ADMIN_MANAGE_ITEMS.length} master data areas.`}
            icon={ADMIN_MANAGE_ITEMS[0].icon}
            path="/admin/manage"
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <AdminActionCard
            title="Imports"
            description={`${ADMIN_IMPORT_ITEMS(roleName).filter((i) => !i.comingSoon).length} import tools available.`}
            icon={ADMIN_IMPORT_ITEMS(roleName)[0]?.icon ?? sections[0].icon}
            path="/admin/imports"
          />
        </Grid>
      </Grid>
    </Box>
  );
}
