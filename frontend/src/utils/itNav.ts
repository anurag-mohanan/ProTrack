/** Match IT section links that may include query filters (category, tab, view). */

export function splitNavPath(path: string): { pathname: string; search: string } {
  const q = path.indexOf('?');
  if (q === -1) return { pathname: path, search: '' };
  return { pathname: path.slice(0, q), search: path.slice(q + 1) };
}

const DEFAULT_TAB_PARAMS = ['category', 'view', 'tab', 'inventory_scope'] as const;

export function matchItNavPath(itemPath: string, pathname: string, search: string): boolean {
  const { pathname: wantPath, search: wantSearch } = splitNavPath(itemPath);
  if (pathname !== wantPath) return false;
  const want = new URLSearchParams(wantSearch);
  const have = new URLSearchParams(search);
  const keys = [...want.keys()];
  if (keys.length === 0) {
    return DEFAULT_TAB_PARAMS.every((key) => !have.get(key));
  }
  return keys.every((key) => have.get(key) === want.get(key));
}

export function isNavItemActive(
  itemPath: string,
  pathname: string,
  search: string,
  options?: { end?: boolean; forceActive?: boolean },
): boolean {
  if (options?.forceActive) return true;
  const { pathname: want, search: wantSearch } = splitNavPath(itemPath);
  if (wantSearch) return matchItNavPath(itemPath, pathname, search);
  if (pathname === want) return matchItNavPath(itemPath, pathname, search);
  if (options?.end) return false;
  const prefix = want.endsWith('/') ? want : `${want}/`;
  return pathname.startsWith(prefix);
}
