import { Box } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminSearchBar } from '../../components/admin/AdminSearchBar';
import { AdminSectionCards } from '../../components/admin/AdminSectionCards';
import { ContentCard } from '../../components/ui/cards';
import {
  ADMIN_AUDIT_ITEMS,
  ADMIN_CREATE_ACTIONS,
  ADMIN_IMPORT_ALL_ITEMS,
  ADMIN_MANAGE_ITEMS,
  ADMIN_SETTINGS_ITEMS,
} from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const roleName = user?.role_name ?? '';

  return (
    <Box>
      <PageHeader
        title="System Administration"
        subtitle="Manage ProTrack configuration and system settings."
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard title="Administrator search">
          <AdminSearchBar />
        </ContentCard>
      </Box>

      <AdminSectionCards title="Create" items={ADMIN_CREATE_ACTIONS} compact />
      <AdminSectionCards title="Manage" items={ADMIN_MANAGE_ITEMS} compact />
      <AdminSectionCards
        title="Import"
        items={ADMIN_IMPORT_ALL_ITEMS(roleName)}
        compact
      />
      <AdminSectionCards title="Settings" items={ADMIN_SETTINGS_ITEMS} compact />
      <AdminSectionCards title="Audit" items={ADMIN_AUDIT_ITEMS} compact />
    </Box>
  );
}
