import { useCallback, useEffect, useState } from 'react';
import { useMediaQuery, useTheme } from '@mui/material';

/** Below this breakpoint the sidebar becomes a temporary drawer. */
export const NAV_COMPACT_BREAKPOINT = 'md' as const;

export const PROTRACK_OPEN_SEARCH_EVENT = 'protrack:open-search';

/** Prefer dynamic viewport height with classic vh fallback (OS zoom / browser chrome). */
export function shellMinHeightSx() {
  return {
    minHeight: '100vh',
    '@supports (min-height: 100dvh)': {
      minHeight: '100dvh',
    },
  } as const;
}

export function viewportCalcHeight(offsetPx: number) {
  return {
    height: `calc(100vh - ${offsetPx}px)`,
    '@supports (height: 100dvh)': {
      height: `calc(100dvh - ${offsetPx}px)`,
    },
  } as const;
}

export function viewportCalcMaxHeight(offsetPx: number) {
  return {
    maxHeight: `calc(100vh - ${offsetPx}px)`,
    '@supports (max-height: 100dvh)': {
      maxHeight: `calc(100dvh - ${offsetPx}px)`,
    },
  } as const;
}

export function requestOpenGlobalSearch() {
  window.dispatchEvent(new CustomEvent(PROTRACK_OPEN_SEARCH_EVENT));
}

/**
 * Shared shell state: compact screens get a hamburger + temporary drawer;
 * desktop keeps the permanent sidebar.
 */
export function useResponsiveShell() {
  const theme = useTheme();
  const isCompact = useMediaQuery(theme.breakpoints.down(NAV_COMPACT_BREAKPOINT));
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (!isCompact) setMobileNavOpen(false);
  }, [isCompact]);

  const openMobileNav = useCallback(() => setMobileNavOpen(true), []);
  const closeMobileNav = useCallback(() => setMobileNavOpen(false), []);
  const toggleMobileNav = useCallback(() => setMobileNavOpen((open) => !open), []);

  return {
    isCompact,
    mobileNavOpen,
    openMobileNav,
    closeMobileNav,
    toggleMobileNav,
    /** Reserved content width for permanent drawer only. */
    contentOffsetPx: isCompact ? 0 : undefined,
  };
}
