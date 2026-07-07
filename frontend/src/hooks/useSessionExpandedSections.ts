import { useCallback, useMemo, useState } from 'react';

function readStorage(storageKey: string): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, boolean>;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeStorage(storageKey: string, value: Record<string, boolean>) {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(storageKey, JSON.stringify(value));
  } catch {
    // Ignore quota or privacy errors.
  }
}

export function useSessionExpandedSections(storageKey: string) {
  const [expandedMap, setExpandedMap] = useState<Record<string, boolean>>(() =>
    readStorage(storageKey),
  );

  const isExpanded = useCallback(
    (sectionId: string, defaultExpanded = true) => {
      if (sectionId in expandedMap) return expandedMap[sectionId];
      return defaultExpanded;
    },
    [expandedMap],
  );

  const setExpanded = useCallback(
    (sectionId: string, expanded: boolean) => {
      setExpandedMap((current) => {
        const next = { ...current, [sectionId]: expanded };
        writeStorage(storageKey, next);
        return next;
      });
    },
    [storageKey],
  );

  const toggleExpanded = useCallback(
    (sectionId: string, defaultExpanded = true) => {
      setExpanded(sectionId, !isExpanded(sectionId, defaultExpanded));
    },
    [isExpanded, setExpanded],
  );

  return useMemo(
    () => ({ isExpanded, setExpanded, toggleExpanded }),
    [isExpanded, setExpanded, toggleExpanded],
  );
}
