import { Box } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { AdminSectionCards } from '../../components/admin/AdminSectionCards';
import { ADMIN_AUDIT_ITEMS } from '../../config/adminNavigation';

export default function AdminAuditHubPage() {
  return (
    <Box>
      <PageHeader
        title="Audit"
        subtitle="Audit logs, deleted records, system health, and import history."
      />
      <AdminSectionCards title="Audit & Compliance" items={ADMIN_AUDIT_ITEMS} />
    </Box>
  );
}
