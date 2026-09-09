import { Tab, Tabs } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { currentItTabPath } from '../../utils/itNav';

export type ITTabItem = { label: string; path: string };

export const IT_INVENTORY_TABS: readonly ITTabItem[] = [
  { label: 'All Assets', path: '/it/assets' },
  { label: 'Computers', path: '/it/assets?category=computer' },
  { label: 'Peripherals & Equipment', path: '/it/assets?category=peripheral' },
  { label: 'Returned / Pending Return', path: '/it/returned-assets' },
  { label: 'Assignments', path: '/it/assets?view=assignments' },
  { label: 'Asset History', path: '/it/assets?view=history' },
];

export const IT_SOFTWARE_TABS: readonly ITTabItem[] = [
  { label: 'Software', path: '/it/software' },
  { label: 'Licenses', path: '/it/software?tab=licenses' },
  { label: 'Assignments', path: '/it/software?tab=assignments' },
  { label: 'Installations', path: '/it/software?tab=installations' },
  { label: 'Renewals / Expiry', path: '/it/software?tab=expiry' },
];

export const IT_SERVICE_TABS: readonly ITTabItem[] = [
  { label: 'Requests', path: '/it/requests' },
  { label: 'Maintenance', path: '/it/maintenance' },
  { label: 'Repairs / Downtime', path: '/it/maintenance?tab=repairs' },
];

export const IT_ADMIN_TABS: readonly ITTabItem[] = [
  { label: 'Master Data', path: '/it/master-data' },
  { label: 'Data Import', path: '/it/data-import' },
  { label: 'Reports', path: '/it/reports' },
  { label: 'Settings', path: '/it/settings' },
  { label: 'IP Pools', path: '/it/networks' },
];

/** @deprecated Use IT_SERVICE_TABS */
export const IT_REQUEST_TABS = IT_SERVICE_TABS;

/** @deprecated Use IT_ADMIN_TABS */
export const IT_SETTINGS_TABS = IT_ADMIN_TABS;

type TabItem = { label: string; path: string };

export function ITSectionSubnav({ items }: { items: readonly TabItem[] }) {
  const location = useLocation();
  const navigate = useNavigate();
  const current = currentItTabPath(items, location.pathname, location.search);

  return (
    <Tabs
      value={current}
      onChange={(_, value: string) => navigate(value)}
      variant="scrollable"
      scrollButtons="auto"
      sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
    >
      {items.map((item) => (
        <Tab key={item.path} value={item.path} label={item.label} sx={{ minHeight: 40 }} />
      ))}
    </Tabs>
  );
}
