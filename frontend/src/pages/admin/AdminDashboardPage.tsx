import { Box } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminSearchBar } from '../../components/admin/AdminSearchBar';
import { AdminSectionCards } from '../../components/admin/AdminSectionCards';
import { ContentCard } from '../../components/ui/cards';
import {
  ADMIN_IMPORT_ALL_ITEMS,
  getAdminAuditItems,
  getAdminCreateActions,
  getAdminManageItems,
  getAdminSettingsItems,
} from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';
import { accessContextFromUser } from '../../utils/permissions';

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);

  const createActions = getAdminCreateActions(access);
  const manageItems = getAdminManageItems(access);
  const importItems = ADMIN_IMPORT_ALL_ITEMS(access);
  const settingsItems = getAdminSettingsItems(access);
  const auditItems = getAdminAuditItems(access);

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

      <AdminSectionCards title="Create" items={createActions} compact />
      <AdminSectionCards title="Manage" items={manageItems} compact />
      <AdminSectionCards title="Import" items={importItems} compact />
      <AdminSectionCards title="Settings" items={settingsItems} compact />
      <AdminSectionCards title="Audit" items={auditItems} compact />
    </Box>
  );
}
