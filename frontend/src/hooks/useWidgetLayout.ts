import { useCallback, useEffect, useState } from 'react';

export interface WidgetLayoutItem {
  id: string;
  visible: boolean;
  order: number;
}

export function useWidgetLayout(storageKey: string, defaultWidgets: string[]) {
  const [widgets, setWidgets] = useState<WidgetLayoutItem[]>(() => {
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw) as WidgetLayoutItem[];
    } catch {
      /* ignore */
    }
    return defaultWidgets.map((id, index) => ({ id, visible: true, order: index }));
  });

  useEffect(() => {
    sessionStorage.setItem(storageKey, JSON.stringify(widgets));
  }, [storageKey, widgets]);

  const toggle = useCallback((id: string) => {
    setWidgets((current) =>
      current.map((item) => (item.id === id ? { ...item, visible: !item.visible } : item)),
    );
  }, []);

  const move = useCallback((id: string, direction: 'up' | 'down') => {
    setWidgets((current) => {
      const sorted = [...current].sort((a, b) => a.order - b.order);
      const index = sorted.findIndex((item) => item.id === id);
      if (index < 0) return current;
      const swapIndex = direction === 'up' ? index - 1 : index + 1;
      if (swapIndex < 0 || swapIndex >= sorted.length) return current;
      const next = [...sorted];
      const temp = next[index].order;
      next[index] = { ...next[index], order: next[swapIndex].order };
      next[swapIndex] = { ...next[swapIndex], order: temp };
      return next;
    });
  }, []);

  const visibleOrdered = [...widgets].filter((w) => w.visible).sort((a, b) => a.order - b.order);

  return { widgets, visibleOrdered, toggle, move };
}
