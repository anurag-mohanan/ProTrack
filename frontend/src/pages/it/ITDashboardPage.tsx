import { useState } from 'react';
import {
  Chip,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import VerifiedUserRoundedIcon from '@mui/icons-material/VerifiedUserRounded';
import AssignmentLateRoundedIcon from '@mui/icons-material/AssignmentLateRounded';
import EventSeatRoundedIcon from '@mui/icons-material/EventSeatRounded';
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
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded';
import RemoveShoppingCartRoundedIcon from '@mui/icons-material/RemoveShoppingCartRounded';
import ShoppingCartRoundedIcon from '@mui/icons-material/ShoppingCartRounded';
import {
  fetchItDashboard,
  fetchItOnboardingTasks,
  itOperationsKeys,
} from '../../api/itOperations';
import {
  fetchProvisioningDashboard,
  itProvisioningKeys,
} from '../../api/itProvisioning';
import { fetchComputerAvailability, itInventoryKeys } from '../../api/itInventory';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ContentCard } from '../../components/ui/cards';
import { KpiMetricCard } from '../../components/ui/design-system';
import { formatCellValue, formatDate } from '../../utils/format';

const WARRANTY_WINDOWS = [7, 30, 60, 90] as const;

export function ITDashboardPage() {
  const navigate = useNavigate();
  const [warrantyDays, setWarrantyDays] = useState<number | undefined>(undefined);
  const query = useQuery({
    queryKey: itOperationsKeys.dashboard(warrantyDays),
    queryFn: () => fetchItDashboard(warrantyDays),
    placeholderData: keepPreviousData,
  });
  const onboardingQuery = useQuery({
    queryKey: itOperationsKeys.onboardingTasks(),
    queryFn: fetchItOnboardingTasks,
  });
  const provisioningQuery = useQuery({
    queryKey: itProvisioningKeys.dashboard(),
    queryFn: fetchProvisioningDashboard,
  });
  const capacityQuery = useQuery({
    queryKey: itInventoryKeys.availability({}),
    queryFn: () => fetchComputerAvailability({}),
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
  const onboardingAttention = data?.onboarding_it_attention ?? 0;
  const totalComputers = data?.total_computers ?? 0;
  const assignedComputers = data?.assigned_computers ?? 0;
  const openComputers = data?.open_computers ?? 0;
  const maintenanceComputers = data?.maintenance_computers ?? 0;
  const retiredComputers = data?.retired_computers ?? 0;
  const employeesWithout = data?.employees_without_computer ?? 0;
  const awaitingReturn = data?.awaiting_return_assets ?? 0;
  const returned = data?.returned_assets ?? 0;
  const retiredAssets = data?.retired_assets ?? 0;
  const disposed = data?.disposed_assets ?? 0;
  const lostDamaged = (data?.lost_assets ?? 0) + (data?.damaged_assets ?? 0);
  const computersWithoutIp = data?.computers_without_ip ?? 0;
  const dataQualityIssues = data?.data_quality_open_issues ?? 0;
  const dataQualityRecords = data?.data_quality_open_records ?? 0;
  const softwareCatalog = data?.software_catalog_count ?? 0;
  const licensePools = data?.license_pool_count ?? 0;
  const licensesExpiring = data?.licenses_expiring_window ?? data?.licenses_expiring_30 ?? 0;
  const licensesExpired = data?.licenses_expired ?? 0;
  const seatsTotal = data?.license_seats_total ?? 0;
  const seatsAssigned = data?.license_seats_assigned ?? 0;
  const seatsAvailable = data?.license_seats_available ?? 0;
  const windowDays = data?.warranty_window_days ?? 30;
  const warrantyExpiring = data?.warranty_expiring_assets ?? 0;
  const warrantyExpired = data?.warranty_expired_assets ?? 0;
  const warrantyMissing = data?.warranty_missing_assets ?? 0;
  const overdueRequests = data?.overdue_it_requests ?? 0;
  const unassignedRequests = data?.unassigned_it_requests ?? 0;
  const movements = data?.recent_movements ?? [];
  const onboardingTasks = onboardingQuery.data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="IT Operations"
        subtitle="Live counts from inventory, Help Desk, licenses and Virtual Seats. Click any figure to open the matching records."
        action={
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Expiry window
            </Typography>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={windowDays}
              onChange={(_, value: number | null) => {
                if (value) setWarrantyDays(value);
              }}
            >
              {WARRANTY_WINDOWS.map((days) => (
                <ToggleButton key={days} value={days}>
                  {days}d
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Stack>
        }
      />

      <Stack spacing={2.5}>
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Total assets (in inventory)"
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
              onClick={() => navigate('/it/assets?status=available')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Assigned"
              value={String(assigned)}
              icon={PersonOutlineRoundedIcon}
              accent="info"
              onClick={() => navigate('/it/assets?view=assignments')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Maintenance"
              value={String(maintenance)}
              icon={BuildRoundedIcon}
              accent="warning"
              onClick={() => navigate('/it/maintenance')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title={`Warranty expiring (${windowDays}d)`}
              value={String(warrantyExpiring)}
              icon={VerifiedUserRoundedIcon}
              accent={warrantyExpiring > 0 ? 'warning' : 'success'}
              subtitle={`${warrantyExpired} expired · ${warrantyMissing} no date`}
              onClick={() =>
                navigate(
                  `/it/assets?warranty_status=expiring_soon&warranty_within_days=${windowDays}`,
                )
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Open IT requests"
              value={String(openRequests)}
              icon={SupportAgentRoundedIcon}
              accent="info"
              subtitle={`${unassignedRequests} unassigned`}
              onClick={() => navigate('/it/requests')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Overdue IT requests"
              value={String(overdueRequests)}
              icon={AssignmentLateRoundedIcon}
              accent={overdueRequests > 0 ? 'error' : 'success'}
              subtitle="Past Help Desk due date"
              onClick={() => navigate('/it/requests?overdue=1')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Data quality"
              value={String(dataQualityRecords)}
              icon={WarningAmberRoundedIcon}
              accent={dataQualityIssues > 0 ? 'warning' : 'success'}
              subtitle={`${dataQualityIssues} issue type(s)`}
              onClick={() => navigate('/it/assets?data_quality=1')}
            />
          </Grid>
        </Grid>

        <Grid container spacing={1.5}>
          <Grid size={{ xs: 6, sm: 3, md: 2 }}>
            <KpiMetricCard
              title="Awaiting return"
              value={String(awaitingReturn)}
              icon={InventoryRoundedIcon}
              accent="warning"
              onClick={() => navigate('/it/assets?status=awaiting_return')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3, md: 2 }}>
            <KpiMetricCard
              title="Returned"
              value={String(returned)}
              icon={InventoryRoundedIcon}
              accent="info"
              onClick={() => navigate('/it/returned-assets')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3, md: 2 }}>
            <KpiMetricCard
              title="Retired"
              value={String(retiredAssets)}
              icon={InventoryRoundedIcon}
              accent="primary"
              onClick={() => navigate('/it/assets?status=retired')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3, md: 2 }}>
            <KpiMetricCard
              title="Disposed"
              value={String(disposed)}
              icon={InventoryRoundedIcon}
              accent="primary"
              onClick={() => navigate('/it/assets?status=disposed')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3, md: 2 }}>
            <KpiMetricCard
              title="Lost / damaged"
              value={String(lostDamaged)}
              icon={InventoryRoundedIcon}
              accent={lostDamaged > 0 ? 'error' : 'primary'}
              onClick={() => navigate('/it/assets?status=lost')}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3, md: 2 }}>
            <KpiMetricCard
              title="Computers without IP"
              value={String(computersWithoutIp)}
              icon={DnsRoundedIcon}
              accent="warning"
              onClick={() => navigate('/it/assets?data_quality=1')}
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
                onClick={() => navigate('/it/assets?category=computer')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Assigned"
                value={String(assignedComputers)}
                icon={PersonOutlineRoundedIcon}
                accent="info"
                onClick={() => navigate('/it/assets?category=computer&status=assigned')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Open"
                value={String(openComputers)}
                icon={CheckCircleOutlineRoundedIcon}
                accent="success"
                onClick={() => navigate('/it/assets?category=computer&status=available')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Maintenance"
                value={String(maintenanceComputers)}
                icon={BuildRoundedIcon}
                accent="warning"
                onClick={() => navigate('/it/assets?category=computer&status=maintenance')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <KpiMetricCard
                title="Retired"
                value={String(retiredComputers)}
                icon={DevicesOtherRoundedIcon}
                accent="primary"
                onClick={() => navigate('/it/assets?category=computer&status=retired')}
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

        <ContentCard title="Consumable stock">
          <Grid container spacing={1.5}>
            {[
              {
                title: 'Low stock',
                value: data?.stock_low_items ?? 0,
                icon: WarningAmberRoundedIcon,
                accent: 'warning' as const,
                to: '/it/inventory?view=low-stock',
              },
              {
                title: 'Out of stock',
                value: data?.stock_out_items ?? 0,
                icon: RemoveShoppingCartRoundedIcon,
                accent: 'error' as const,
                to: '/it/inventory?view=low-stock',
              },
              {
                title: 'Upcoming shortage',
                value: data?.stock_upcoming_shortages ?? 0,
                icon: AssignmentLateRoundedIcon,
                accent: 'error' as const,
                to: '/it/reports?report=upcoming_demand',
              },
              {
                title: 'Pending restock',
                value: data?.stock_pending_restock ?? 0,
                icon: ShoppingCartRoundedIcon,
                accent: 'info' as const,
                to: '/it/inventory?view=restock',
              },
              {
                title: 'Incoming units',
                value: data?.stock_incoming_units ?? 0,
                icon: LocalShippingRoundedIcon,
                accent: 'info' as const,
                to: '/it/inventory?view=restock',
              },
              {
                title: 'Reorder needed',
                value: data?.stock_reorder_needed ?? 0,
                icon: InventoryRoundedIcon,
                accent: 'warning' as const,
                to: '/it/inventory?stock_status=reorder',
              },
            ].map((card) => (
              <Grid key={card.title} size={{ xs: 6, sm: 4, md: 2 }}>
                <KpiMetricCard
                  title={card.title}
                  value={String(card.value)}
                  icon={card.icon}
                  accent={card.value > 0 ? card.accent : 'success'}
                  onClick={() => navigate(card.to)}
                />
              </Grid>
            ))}
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
                title="License seats"
                value={String(seatsTotal)}
                icon={AppsRoundedIcon}
                accent="info"
                subtitle={`${seatsAssigned} assigned · ${seatsAvailable} available · ${licensePools} pools`}
                onClick={() => navigate('/it/software?tab=licenses')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <KpiMetricCard
                title={`Expiring (${windowDays}d)`}
                value={String(licensesExpiring)}
                icon={WarningAmberRoundedIcon}
                accent="warning"
                onClick={() => navigate('/it/software?tab=expiry')}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <KpiMetricCard
                title="Expired"
                value={String(licensesExpired)}
                icon={EventBusyRoundedIcon}
                accent="error"
                onClick={() => navigate('/it/software?tab=expiry')}
              />
            </Grid>
          </Grid>
        </ContentCard>

        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Virtual Seats"
              value={String(data?.virtual_seats_total ?? 0)}
              icon={EventSeatRoundedIcon}
              accent={(data?.virtual_seats_incomplete ?? 0) > 0 ? 'warning' : 'primary'}
              subtitle={`${data?.virtual_seats_incomplete ?? 0} incomplete · ${data?.virtual_seat_conflicts ?? 0} conflicts`}
              onClick={() => navigate('/it/virtual-seats')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="IP pools"
              value={String(networks)}
              icon={LanRoundedIcon}
              accent="primary"
              onClick={() => navigate('/it/networks')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Computers with IP"
              value={String(allocatedIps)}
              icon={DnsRoundedIcon}
              accent="info"
              onClick={() => navigate('/it/assets?category=computer')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <KpiMetricCard
              title="Pending onboarding IT"
              value={String(pendingOnboarding)}
              icon={HowToRegRoundedIcon}
              accent={onboardingAttention > 0 ? 'error' : 'warning'}
              subtitle={
                onboardingAttention > 0
                  ? `${onboardingAttention} need attention (no request, blocked or overdue)`
                  : 'Unresolved IT checklist tasks'
              }
              onClick={() => navigate('/hr/onboarding')}
            />
          </Grid>
        </Grid>

        {provisioningQuery.data ? (
          <ContentCard
            title="New employee IT provisioning"
            subtitle="Demand from hire-with-IT requests (not yet completed)."
          >
            <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
              <Grid size={{ xs: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">
                  Open requests
                </Typography>
                <Typography variant="h6">{provisioningQuery.data.open_it_requests}</Typography>
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">
                  Overdue
                </Typography>
                <Typography variant="h6">{provisioningQuery.data.overdue_requests}</Typography>
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">
                  Waiting for license
                </Typography>
                <Typography variant="h6">
                  {provisioningQuery.data.waiting_for_software_license}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <Typography variant="caption" color="text.secondary">
                  Ready for joining
                </Typography>
                <Typography variant="h6">{provisioningQuery.data.ready_for_joining}</Typography>
              </Grid>
            </Grid>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              Hardware demand
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mb: 1 }}>
              {(provisioningQuery.data.hardware_demand.by_computer_type || []).map((row) =>
                row.required ? (
                  <Chip
                    key={row.code}
                    size="small"
                    label={`${row.label}: ${row.required}`}
                  />
                ) : null,
              )}
              <Chip
                size="small"
                label={`Monitors: ${provisioningQuery.data.hardware_demand.monitors_required ?? 0}`}
              />
              <Chip
                size="small"
                label={`3D mice: ${provisioningQuery.data.hardware_demand.mice_3d_required ?? 0}`}
              />
            </Stack>
            {(provisioningQuery.data.software_demand || []).length ? (
              <>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                  Software / license demand
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Software</TableCell>
                      <TableCell align="right">Requested</TableCell>
                      <TableCell align="right">Available</TableCell>
                      <TableCell align="right">Shortage</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {provisioningQuery.data.software_demand.map((row) => (
                      <TableRow key={row.software_id}>
                        <TableCell>{row.software_name || row.software_id}</TableCell>
                        <TableCell align="right">{row.requested}</TableCell>
                        <TableCell align="right">{row.available}</TableCell>
                        <TableCell align="right">{row.shortage}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            ) : null}
          </ContentCard>
        ) : null}

        {capacityQuery.data?.summary.length ? (
          <ContentCard
            title="Free computers by type and shift"
            subtitle="Same shift rule as assignment validation. Click to open the availability view."
            action={
              <Chip
                size="small"
                clickable
                label="Open availability"
                onClick={() => navigate('/it/inventory?view=availability')}
              />
            }
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Type</TableCell>
                  <TableCell align="right">Computers</TableCell>
                  {capacityQuery.data.shifts.map((s) => (
                    <TableCell key={s.shift_id} align="right">
                      Free · {s.shift_display}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {capacityQuery.data.summary.map((row) => (
                  <TableRow key={row.seat_type}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{row.total}</TableCell>
                    {capacityQuery.data.shifts.map((s) => (
                      <TableCell key={s.shift_id} align="right">
                        {row.by_shift[s.shift_code] ?? 0}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ContentCard>
        ) : null}

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

        <ContentCard
          title="Recent asset movements"
          subtitle="Latest assignment starts and returns from asset assignment history."
        >
          {movements.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No asset assignments recorded yet.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Asset</TableCell>
                  <TableCell>Employee</TableCell>
                  <TableCell>Movement</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {movements.map((row, index) => (
                  <TableRow key={`${row.asset_id}-${row.user_id}-${index}`}>
                    <TableCell>{formatDate(row.date) || '—'}</TableCell>
                    <TableCell>
                      <RouterLink to={`/it/assets?search=${encodeURIComponent(row.asset_number)}`}>
                        {row.asset_number}
                      </RouterLink>
                    </TableCell>
                    <TableCell>
                      <RouterLink to={`/it/accounts?user=${row.user_id}&status=all`}>
                        {row.user_name}
                      </RouterLink>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={row.movement === 'assigned' ? 'info' : 'default'}
                        label={row.movement === 'assigned' ? 'Assigned' : 'Returned'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>
      </Stack>
    </PageContainer>
  );
}
