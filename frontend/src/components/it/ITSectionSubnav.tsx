import { Tab, Tabs } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';

export const IT_INVENTORY_TABS = [
  { label: 'Assets', path: '/it/assets' },
  { label: 'Computers', path: '/it/computers' },
  { label: 'Returned', path: '/it/returned-assets' },
  { label: 'People', path: '/it/accounts' },
  { label: 'Catalog', path: '/it/master-data' },
] as const;

export const IT_REQUEST_TABS = [
  { label: 'Requests', path: '/it/requests' },
  { label: 'Maintenance', path: '/it/maintenance' },
] as const;

export const IT_SETTINGS_TABS = [
  { label: 'Settings', path: '/it/settings' },
  { label: 'Data import', path: '/it/data-import' },
  { label: 'Reports', path: '/it/reports' },
] as const;

type TabItem = { label: string; path: string };

export function ITSectionSubnav({ items }: { items: readonly TabItem[] }) {
  const location = useLocation();
  const navigate = useNavigate();
  const current =
    items.find((item) => location.pathname === item.path || location.pathname.startsWith(`${item.path}/`))
      ?.path ?? items[0]?.path;

  return (
    <Tabs
      value={current}
      onChange={(_, value: string) => navigate(value)}
      sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
    >
      {items.map((item) => (
        <Tab key={item.path} value={item.path} label={item.label} sx={{ minHeight: 40 }} />
      ))}
    </Tabs>
  );
}
