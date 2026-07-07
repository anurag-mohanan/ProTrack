import { useCallback, useMemo, useState } from 'react';

export interface DrillDownLevel {
  id: string;
  label: string;
  type: 'customer' | 'project' | 'designer' | 'team' | 'report';
  meta?: Record<string, string>;
}

export function useDrillDown(initial?: DrillDownLevel[]) {
  const [stack, setStack] = useState<DrillDownLevel[]>(initial ?? []);

  const push = useCallback((level: DrillDownLevel) => {
    setStack((current) => {
      const existing = current.findIndex((item) => item.id === level.id && item.type === level.type);
      if (existing >= 0) return current.slice(0, existing + 1);
      return [...current, level];
    });
  }, []);

  const pop = useCallback(() => {
    setStack((current) => current.slice(0, -1));
  }, []);

  const reset = useCallback(() => setStack([]), []);

  const navigateTo = useCallback((index: number) => {
    setStack((current) => current.slice(0, index + 1));
  }, []);

  const current = stack[stack.length - 1] ?? null;

  return useMemo(
    () => ({ stack, current, push, pop, reset, navigateTo }),
    [stack, current, push, pop, reset, navigateTo],
  );
}
