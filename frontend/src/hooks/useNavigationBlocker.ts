import { useCallback, useEffect } from 'react';
import { useBlocker } from 'react-router-dom';

export function useNavigationBlocker(
  when: boolean,
  message = 'You have unsaved changes. Leave without saving?',
) {
  const blocker = useBlocker(when);

  useEffect(() => {
    if (!when) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [when, message]);

  const confirmLeave = useCallback(() => {
    if (blocker.state === 'blocked') blocker.proceed();
  }, [blocker]);

  const cancelLeave = useCallback(() => {
    if (blocker.state === 'blocked') blocker.reset();
  }, [blocker]);

  return {
    blocked: blocker.state === 'blocked',
    confirmLeave,
    cancelLeave,
  };
}
