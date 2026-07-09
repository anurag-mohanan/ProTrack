import { Box } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminSectionCards } from '../../components/admin/AdminSectionCards';
import { getAdminAuditItems } from '../../config/adminNavigation';
import { useAuth } from '../../context/AuthContext';

export default function AdminAuditHubPage() {
  const { user } = useAuth();
  return (
    <Box>
      <PageHeader
        title="Audit"
        subtitle="Audit logs, deleted records, system health, and import history."
      />
      <AdminSectionCards title="Audit & Compliance" items={getAdminAuditItems(user?.role_name ?? '')} />
    </Box>
  );
}
