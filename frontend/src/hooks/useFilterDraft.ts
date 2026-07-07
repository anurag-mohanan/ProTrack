import { useCallback, useState } from 'react';

export function useFilterDraft<T>(initialValue: T) {
  const [applied, setApplied] = useState<T>(initialValue);
  const [draft, setDraft] = useState<T>(initialValue);

  const apply = useCallback(() => {
    setApplied(draft);
  }, [draft]);

  const resetDraft = useCallback(() => {
    setDraft(applied);
  }, [applied]);

  const clearAll = useCallback(() => {
    setApplied(initialValue);
    setDraft(initialValue);
  }, [initialValue]);

  const setBoth = useCallback((next: T) => {
    setApplied(next);
    setDraft(next);
  }, []);

  return {
    applied,
    draft,
    setDraft,
    setApplied: setBoth,
    apply,
    resetDraft,
    clearAll,
  };
}
