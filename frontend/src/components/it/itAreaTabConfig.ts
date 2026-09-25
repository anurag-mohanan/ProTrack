import { matchItNavPath } from '../../utils/itNav';

export type ITAreaTab = { label: string; path: string };

/** Views of the Assets & Inventory area (one sidebar entry). */
export const IT_ASSET_AREA_TABS: readonly ITAreaTab[] = [
  { label: 'Physical assets', path: '/it/assets' },
  { label: 'Computers', path: '/it/assets?category=computer' },
  { label: 'Peripherals', path: '/it/assets?category=peripheral' },
  { label: 'Network devices', path: '/it/assets?category=network_equipment' },
  { label: 'Inventory', path: '/it/inventory' },
  { label: 'Virtual seats', path: '/it/virtual-seats' },
  { label: 'Low stock', path: '/it/inventory?view=low-stock' },
  { label: 'Stock movements', path: '/it/inventory?view=movements' },
  { label: 'Restock', path: '/it/inventory?view=restock' },
  { label: 'Availability', path: '/it/inventory?view=availability' },
  { label: 'Assignments', path: '/it/assets?view=assignments' },
  { label: 'History', path: '/it/assets?view=history' },
  { label: 'Maintenance', path: '/it/maintenance' },
  { label: 'Returns', path: '/it/returned-assets' },
  { label: 'By employee', path: '/it/accounts' },
];

/** Views of Software & Licenses (one sidebar entry). */
export const IT_SOFTWARE_AREA_TABS: readonly ITAreaTab[] = [
  { label: 'Software', path: '/it/software' },
  { label: 'Licenses', path: '/it/software?tab=licenses' },
  { label: 'Assignments', path: '/it/software?tab=assignments' },
  { label: 'Installations', path: '/it/software?tab=installations' },
  { label: 'Expiring', path: '/it/software?tab=expiry' },
  { label: 'Requests', path: '/it/software?tab=requirements' },
  { label: 'Packages', path: '/it/software?tab=packages' },
];

/** Configuration pages (one sidebar entry: Administration). */
export const IT_ADMIN_AREA_TABS: readonly ITAreaTab[] = [
  { label: 'Settings', path: '/it/settings' },
  { label: 'Master data', path: '/it/master-data' },
  { label: 'Data import', path: '/it/data-import' },
  { label: 'Networks & IPs', path: '/it/networks' },
  { label: 'Computer network IDs', path: '/it/computers' },
];

export const IT_ASSET_AREA_PATHS = [
  '/it/assets',
  '/it/inventory',
  '/it/virtual-seats',
  '/it/maintenance',
  '/it/returned-assets',
  '/it/accounts',
];
export const IT_ADMIN_AREA_PATHS = [
  '/it/settings',
  '/it/master-data',
  '/it/data-import',
  '/it/networks',
  '/it/computers',
];

export function currentAreaTab(
  items: readonly ITAreaTab[],
  pathname: string,
  search: string,
): string | false {
  const hit = items.find((item) => matchItNavPath(item.path, pathname, search));
  return hit ? hit.path : false;
}
