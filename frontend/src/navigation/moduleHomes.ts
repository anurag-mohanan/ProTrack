/** Resolve module homepage for nested routes (layout-level back control). */

export type ModuleHome = {
  homePath: string;
  homeLabel: string;
};

/**
 * Returns the module home when the current path is a nested child.
 * Returns null on the home itself or on single-page modules.
 */
export function resolveModuleHome(pathname: string): ModuleHome | null {
  const path = pathname.replace(/\/+$/, '') || '/';

  if (path.startsWith('/hr/') && path !== '/hr') {
    return { homePath: '/hr', homeLabel: 'HR Dashboard' };
  }

  if (path === '/projects/archived') {
    return { homePath: '/projects', homeLabel: 'Projects' };
  }
  if (path.startsWith('/projects/') && path !== '/projects') {
    return { homePath: '/projects', homeLabel: 'Projects' };
  }

  if (
    path.startsWith('/admin/') &&
    path !== '/admin' &&
    path !== '/admin/dashboard'
  ) {
    return { homePath: '/admin/dashboard', homeLabel: 'Admin' };
  }

  return null;
}
