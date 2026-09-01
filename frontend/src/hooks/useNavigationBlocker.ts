import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Unsaved-changes guard compatible with BrowserRouter (no data router required).
 * - Warns on tab close / refresh via beforeunload
 * - Intercepts browser Back and surfaces a confirm callback for in-app dialogs
 */
export function useNavigationBlocker(
  when: boolean,
  message = 'You have unsaved changes. Leave without saving?',
) {
  const whenRef = useRef(when);
  whenRef.current = when;
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    if (!when) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [when, message]);

  useEffect(() => {
    if (!when) return;

    const pushGuard = () => {
      window.history.pushState({ navigationBlocker: true }, '', window.location.href);
    };

    pushGuard();

    const onPopState = () => {
      if (!whenRef.current) return;
      setBlocked(true);
      pushGuard();
    };

    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [when]);

  const confirmLeave = useCallback(() => {
    setBlocked(false);
    whenRef.current = false;
    window.history.back();
  }, []);

  const cancelLeave = useCallback(() => {
    setBlocked(false);
  }, []);

  return {
    blocked,
    confirmLeave,
    cancelLeave,
  };
}
