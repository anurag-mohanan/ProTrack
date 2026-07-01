import { useCallback, useState } from 'react';

const STORAGE_KEY = 'protrack-admin-nav-expanded';

function readStored(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

export function useAdminNavExpanded(sectionId: string, defaultExpanded = false) {
  const [expanded, setExpandedState] = useState<boolean>(() => {
    const stored = readStored();
    return stored[sectionId] ?? defaultExpanded;
  });

  const setExpanded = useCallback(
    (value: boolean) => {
      setExpandedState(value);
      const stored = readStored();
      stored[sectionId] = value;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
    },
    [sectionId],
  );

  const toggle = useCallback(() => {
    setExpanded(!expanded);
  }, [expanded, setExpanded]);

  return { expanded, setExpanded, toggle };
}
