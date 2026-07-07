import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

function stableSerialize<T>(value: T): string {
  return JSON.stringify(value);
}

export function useDirtyForm<T>(baseline: T, active: boolean) {
  const [form, setForm] = useState<T>(baseline);
  const baselineRef = useRef(baseline);

  useEffect(() => {
    if (!active) return;
    baselineRef.current = baseline;
    setForm(baseline);
  }, [active, baseline]);

  const isDirty = useMemo(
    () => stableSerialize(form) !== stableSerialize(baselineRef.current),
    [form],
  );

  const reset = useCallback(() => {
    setForm(baselineRef.current);
  }, []);

  const markClean = useCallback((nextBaseline?: T) => {
    const resolved = nextBaseline ?? form;
    baselineRef.current = resolved;
    setForm(resolved);
  }, [form]);

  return { form, setForm, isDirty, reset, markClean };
}
