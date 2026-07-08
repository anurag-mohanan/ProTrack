import { useCallback } from 'react';
import type { NavigateFunction } from 'react-router-dom';
import { useLocation, useNavigate } from 'react-router-dom';

export interface BackNavigationState {
  from?: string;
  scrollY?: number;
  filters?: Record<string, unknown>;
}

export function useBackNavigation(fallbackPath: string) {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as BackNavigationState;

  const goBack = useCallback(() => {
    if (state.from) {
      navigate(state.from, {
        state: {
          restoreScrollY: state.scrollY,
          restoreFilters: state.filters,
        },
      });
      return;
    }
    navigate(fallbackPath);
  }, [fallbackPath, navigate, state.filters, state.from, state.scrollY]);

  return { goBack, from: state.from };
}

export function buildDetailNavigationState(fromPath: string): BackNavigationState {
  return {
    from: fromPath,
    scrollY: window.scrollY,
    filters: Object.fromEntries(new URLSearchParams(window.location.search)),
  };
}

export function navigateWithBack(navigate: NavigateFunction, path: string) {
  const from = `${window.location.pathname}${window.location.search}`;
  navigate(path, { state: buildDetailNavigationState(from) });
}
