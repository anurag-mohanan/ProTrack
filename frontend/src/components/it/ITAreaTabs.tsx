import { Tab, Tabs } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { currentAreaTab, type ITAreaTab } from './itAreaTabConfig';

/** In-page views for an IT area. The sidebar lists areas only, never these views. */
export function ITAreaTabs({ items }: { items: readonly ITAreaTab[] }) {
  const location = useLocation();
  const navigate = useNavigate();
  const current = currentAreaTab(items, location.pathname, location.search);

  return (
    <Tabs
      value={current}
      onChange={(_, value: string) => navigate(value)}
      variant="scrollable"
      scrollButtons="auto"
      aria-label="Area views"
      sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
    >
      {items.map((item) => (
        <Tab key={item.path} value={item.path} label={item.label} sx={{ minHeight: 40 }} />
      ))}
    </Tabs>
  );
}
