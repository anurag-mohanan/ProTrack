import { Chip, Grid, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import PersonOutlineRoundedIcon from '@mui/icons-material/PersonOutlineRounded';
import BuildRoundedIcon from '@mui/icons-material/BuildRounded';
import SupportAgentRoundedIcon from '@mui/icons-material/SupportAgentRounded';
import LanRoundedIcon from '@mui/icons-material/LanRounded';
import DnsRoundedIcon from '@mui/icons-material/DnsRounded';
import HowToRegRoundedIcon from '@mui/icons-material/HowToRegRounded';
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded';
import AppsRoundedIcon from '@mui/icons-material/AppsRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import EventBusyRoundedIcon from '@mui/icons-material/EventBusyRounded';
import {
  fetchItDashboard,
  fetchItOnboardingTasks,
  itOperationsKeys,
} from '../../api/itOperations';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ContentCard, DashboardCard } from '../../components/ui/cards';
import { KpiMetricCard } from '../../components/ui/design-system';
import { formatCellValue, formatDate } from '../../utils/format';

export function ITDashboardPage() {
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: itOperationsKeys.dashboard(),
    queryFn: fetchItDashboard,
  });
  const onboardingQuery = useQuery({
    queryKey: itOperationsKeys.onboardingTasks(),
    queryFn: fetchItOnboardingTasks,
  });

  if (query.isLoading) {
    return <LoadingState message="Loading IT dashboard…" />;
  }

  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load IT dashboard"
        onRetry={() => void query.refetch()}
      />
    );
  }

  const data = query.data;
  const total = data?.total_assets ?? 0;
  const available = data?.available_assets ?? 0;
  const assigned = data?.assigned_assets ?? 0;
  const maintenance = data?.maintenance_assets ?? 0;
  const openRequests = data?.open_it_requests ?? 0;
  const networks = data?.networks ?? 0;
  const allocatedIps = data?.allocated_ips ?? 0;
  const pendingOnboarding = data?.pending_onboarding_tasks ?? 0;
  const totalComputers = data?.total_computers ?? 0;
  const assignedComputers = data?.assigned_computers ?? 0;
  const openComputers = data?.open_computers ?? 0;
  const maintenanceComputers = data?.maintenance_computers ?? 0;
  const retiredComputers = data?.retired_computers ?? 0;
  const employeesWithout = data?.employees_without_computer ?? 0;
  const softwareCatalog = data?.software_catalog_count ?? 0;
  const licensePools = data?.license_pool_count ?? 0;
  const licensesExpiring = data?.licenses_expiring_30 ?? 0;
  const licensesExpired = data?.licenses_expired ?? 0;
  const onboardingTasks = onboardingQuery.data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="IT Operations"
        subtitle="Asset register, computer inventory, network pools, and open IT requests."
      />

      <Stack spacing={2.5}>
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Total assets"
              value={String(total)}
              icon={InventoryRoundedIcon}
              accent="primary"
              onClick={() => navigate('/it/assets')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Available"
              value={String(available)}
              icon={CheckCircleOutlineRoundedIcon}
              accent="success"
              onClick={() => navigate('/it/assets')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Assigned"
              value={String(assigned)}
              icon={PersonOutlineRoundedIcon}
              accent="info"
              onClick={() => navigate('/it/assets')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Maintenance"
              value={String(maintenance)}
              icon={BuildRoundedIcon}
              accent="warning"
              onClick={() => navigate('/it/assets')}
            />
          </Grid>
        </Grid>

        <ContentCard title="Computer availability">
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Total"
                value={String(totalComputers)}
                icon={DevicesOtherRoundedIcon}
                accent="primary"
                onClick={() => navigate('/it/computers')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Assigned"
                value={String(assignedComputers)}
                icon={PersonOutlineRoundedIcon}
                accent="info"
                onClick={() => navigate('/it/computers?availability=assigned')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Open"
                value={String(openComputers)}
                icon={CheckCircleOutlineRoundedIcon}
                accent="success"
                onClick={() => navigate('/it/computers?availability=open')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Maintenance"
                value={String(maintenanceComputers)}
                icon={BuildRoundedIcon}
                accent="warning"
                onClick={() => navigate('/it/computers?availability=maintenance')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Retired"
                value={String(retiredComputers)}
                icon={DevicesOtherRoundedIcon}
                accent="primary"
                onClick={() => navigate('/it/computers?availability=retired')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="No computer"
                value={String(employeesWithout)}
                icon={HowToRegRoundedIcon}
                accent="warning"
                onClick={() => navigate('/it/accounts')}
              />
            </Grid>
          </Grid>
        </ContentCard>

        <ContentCard title="Software & licenses">
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <KpiMetricCard
                title="Catalog"
                value={String(softwareCatalog)}
                icon={AppsRoundedIcon}
                accent="primary"
                onClick={() => navigate('/it/software')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <KpiMetricCard
                title="License pools"
                value={String(licensePools)}
                icon={DevicesOtherRoundedIcon}
                accent="info"
                onClick={() => navigate('/it/software')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <KpiMetricCard
                title="Expiring (30d)"
                value={String(licensesExpiring)}
                icon={WarningAmberRoundedIcon}
                accent="warning"
                onClick={() => navigate('/it/software')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <KpiMetricCard
                title="Expired"
                value={String(licensesExpired)}
                icon={EventBusyRoundedIcon}
                accent="error"
                onClick={() => navigate('/it/software')}
              />
            </Grid>
          </Grid>
        </ContentCard>

        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Open IT requests"
              value={String(openRequests)}
              icon={SupportAgentRoundedIcon}
              accent="error"
              onClick={() => navigate('/it/requests')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Networks"
              value={String(networks)}
              icon={LanRoundedIcon}
              accent="primary"
              onClick={() => navigate('/it/networks')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Allocated IPs"
              value={String(allocatedIps)}
              icon={DnsRoundedIcon}
              accent="info"
              onClick={() => navigate('/it/networks')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Pending onboarding IT"
              value={String(pendingOnboarding)}
              icon={HowToRegRoundedIcon}
              accent="warning"
              subtitle="Checklist items awaiting IT"
              onClick={() => navigate('/hr/onboarding')}
            />
          </Grid>
        </Grid>

        <ContentCard
          title="Pending IT onboarding tasks"
          subtitle="Complete these from Onboarding, or open the linked Help Desk ticket."
        >
          {onboardingQuery.isLoading ? (
            <Typography variant="body2" color="text.secondary">
              Loading tasks…
            </Typography>
          ) : onboardingTasks.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No pending IT onboarding checklist items.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Employee</TableCell>
                  <TableCell>Task</TableCell>
                  <TableCell>Joining</TableCell>
                  <TableCell>Ticket</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {onboardingTasks.map((task) => (
                  <TableRow
                    key={task.item_id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => navigate('/hr/onboarding')}
                  >
                    <TableCell>
                      {task.employee_name}
                      {task.employee_code ? (
                        <Chip size="small" label={task.employee_code} sx={{ ml: 1 }} />
                      ) : null}
                    </TableCell>
                    <TableCell>{task.item_text}</TableCell>
                    <TableCell>{formatDate(task.joining_date) || '—'}</TableCell>
                    <TableCell>{formatCellValue(task.help_ticket_id)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>

        <ContentCard title="Quick links" subtitle="Jump into common IT Operations workspaces.">
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <DashboardCard
                title="Assets"
                subtitle="Register and assignments"
                icon={InventoryRoundedIcon}
                accent="primary"
                onClick={() => navigate('/it/assets')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <DashboardCard
                title="Computers"
                subtitle="Named workstations"
                icon={DevicesOtherRoundedIcon}
                accent="info"
                onClick={() => navigate('/it/computers')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <DashboardCard
                title="Networks"
                subtitle="CIDR pools and IPs"
                icon={LanRoundedIcon}
                accent="secondary"
                onClick={() => navigate('/it/networks')}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <DashboardCard
                title="IT Requests"
                subtitle="Open help-desk tickets"
                icon={SupportAgentRoundedIcon}
                accent="warning"
                onClick={() => navigate('/it/requests')}
              />
            </Grid>
          </Grid>
        </ContentCard>
      </Stack>
    </PageContainer>
  );
}
