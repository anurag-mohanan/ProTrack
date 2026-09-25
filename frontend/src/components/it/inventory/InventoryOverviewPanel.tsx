import { Box, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import ComputerRoundedIcon from '@mui/icons-material/ComputerRounded';
import DesktopWindowsRoundedIcon from '@mui/icons-material/DesktopWindowsRounded';
import EventSeatRoundedIcon from '@mui/icons-material/EventSeatRounded';
import LaptopRoundedIcon from '@mui/icons-material/LaptopRounded';
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded';
import RemoveShoppingCartRoundedIcon from '@mui/icons-material/RemoveShoppingCartRounded';
import ReportProblemRoundedIcon from '@mui/icons-material/ReportProblemRounded';
import ShoppingCartRoundedIcon from '@mui/icons-material/ShoppingCartRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import { useNavigate } from 'react-router-dom';
import type { InventoryOverview } from '../../../types/itInventory';
import { ContentCard } from '../../ui/cards';
import { KpiMetricCard } from '../../ui/design-system';
import { StockStatusChip } from './StockStatusChip';

const GROUP_COLUMNS: { key: string; label: string }[] = [
  { key: 'total', label: 'Total' },
  { key: 'in_stock', label: 'In stock' },
  { key: 'assigned', label: 'Assigned' },
  { key: 'reserved', label: 'Reserved' },
  { key: 'maintenance', label: 'Maintenance' },
  { key: 'awaiting_return', label: 'Pending return' },
];

export function InventoryOverviewPanel({ data }: { data: InventoryOverview }) {
  const navigate = useNavigate();
  const kpis = [
    {
      title: 'Workstations in stock',
      value: data.computers.workstations_in_stock,
      icon: DesktopWindowsRoundedIcon,
      to: '/it/inventory?view=availability',
    },
    {
      title: 'Laptops in stock',
      value: data.computers.laptops_in_stock,
      icon: LaptopRoundedIcon,
      to: '/it/inventory?view=availability',
    },
    {
      title: 'Computers assigned',
      value: data.computers.assigned,
      icon: ComputerRoundedIcon,
      to: '/it/assets?category=computer',
    },
    {
      title: 'Monitors in stock',
      value: data.monitors.in_stock,
      subtitle: `${data.monitors.assigned} assigned of ${data.monitors.total}`,
      icon: DesktopWindowsRoundedIcon,
      to: '/it/assets?category=peripheral',
    },
    {
      title: 'Low stock items',
      value: data.consumables.low_stock,
      icon: WarningAmberRoundedIcon,
      accent: data.consumables.low_stock ? ('warning' as const) : undefined,
      to: '/it/inventory?view=low-stock',
    },
    {
      title: 'Out of stock',
      value: data.consumables.out_of_stock,
      icon: RemoveShoppingCartRoundedIcon,
      accent: data.consumables.out_of_stock ? ('error' as const) : undefined,
      to: '/it/inventory?view=low-stock',
    },
    {
      title: 'Upcoming shortages',
      value: data.upcoming_shortages,
      subtitle: 'Open onboarding vs free stock',
      icon: ReportProblemRoundedIcon,
      accent: data.upcoming_shortages ? ('error' as const) : undefined,
      to: '/it/reports?report=upcoming_demand',
    },
    {
      title: 'Pending restock',
      value: data.consumables.pending_restock,
      icon: ShoppingCartRoundedIcon,
      to: '/it/inventory?view=restock',
    },
    {
      title: 'Incoming units',
      value: data.consumables.incoming_units,
      icon: LocalShippingRoundedIcon,
      to: '/it/inventory?view=restock',
    },
    {
      title: 'Incomplete seats',
      value: data.virtual_seats.incomplete,
      subtitle: `${data.virtual_seats.complete} complete of ${data.virtual_seats.total_seats}`,
      icon: EventSeatRoundedIcon,
      accent: data.virtual_seats.incomplete ? ('warning' as const) : undefined,
      to: '/it/virtual-seats?setup_status=incomplete',
    },
  ];

  return (
    <Stack spacing={2.5}>
      <Box
        sx={{
          display: 'grid',
          gap: 1.5,
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(5, 1fr)' },
        }}
      >
        {kpis.map((kpi) => (
          <KpiMetricCard
            key={kpi.title}
            compact
            title={kpi.title}
            value={String(kpi.value)}
            subtitle={kpi.subtitle}
            icon={kpi.icon}
            accent={kpi.accent}
            onClick={() => navigate(kpi.to)}
          />
        ))}
      </Box>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
        <ContentCard title="Physical assets by category">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Category</TableCell>
                {GROUP_COLUMNS.map((c) => (
                  <TableCell key={c.key} align="right">
                    {c.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.by_group.map((row) => (
                <TableRow key={row.group}>
                  <TableCell>{row.label}</TableCell>
                  {GROUP_COLUMNS.map((c) => (
                    <TableCell key={c.key} align="right">
                      {Number(row[c.key] ?? 0)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ContentCard>
        <ContentCard title="Free now, by component">
          {data.available_by_kind.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No free assets or stock recorded.
            </Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Component</TableCell>
                  <TableCell align="right">Assets</TableCell>
                  <TableCell align="right">Stock</TableCell>
                  <TableCell align="right">Total</TableCell>
                  <TableCell>Stock status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.available_by_kind.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell align="right">{row.assets_available}</TableCell>
                    <TableCell align="right">{row.stock_available}</TableCell>
                    <TableCell align="right">{row.available}</TableCell>
                    <TableCell>
                      <StockStatusChip status={row.stock_status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ContentCard>
      </Box>
      <ContentCard title="Upcoming onboarding demand (not deducted)">
        {data.upcoming_demand.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No open onboarding hardware requirements.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Requirement</TableCell>
                <TableCell align="right">Required</TableCell>
                <TableCell align="right">Reserved</TableCell>
                <TableCell align="right">Free now</TableCell>
                <TableCell align="right">Incoming</TableCell>
                <TableCell align="right">Projected</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.upcoming_demand.map((row) => (
                <TableRow key={row.key} sx={row.shortage ? { bgcolor: (t) => alpha(t.palette.error.main, 0.06) } : undefined}>
                  <TableCell>{row.label}</TableCell>
                  <TableCell align="right">{row.required}</TableCell>
                  <TableCell align="right">{row.committed}</TableCell>
                  <TableCell align="right">{row.available}</TableCell>
                  <TableCell align="right">{row.incoming}</TableCell>
                  <TableCell align="right" sx={{ color: row.shortage ? 'error.main' : undefined, fontWeight: 700 }}>
                    {row.projected}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ContentCard>
    </Stack>
  );
}
