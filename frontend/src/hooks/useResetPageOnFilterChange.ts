import { useEffect, useRef } from 'react';

/**
 * Reset pagination to page 1 when filters/search change.
 * Skips the initial mount so page navigation is not interrupted.
 */
export function useResetPageOnFilterChange(
  filterKey: string | number | undefined,
  resetPage: () => void,
) {
  const previousFilterKeyRef = useRef(filterKey);

  useEffect(() => {
    if (previousFilterKeyRef.current === filterKey) {
      return;
    }
    previousFilterKeyRef.current = filterKey;
    resetPage();
  }, [filterKey, resetPage]);
}
