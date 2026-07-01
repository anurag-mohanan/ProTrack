import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

/** Opens a create drawer when the URL contains ?create=1 (used by Admin Create hub). */
export function useOpenCreateFromQuery(onOpen: () => void) {
  const [searchParams, setSearchParams] = useSearchParams();
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;

  useEffect(() => {
    if (searchParams.get('create') !== '1') return;
    onOpenRef.current();
    const next = new URLSearchParams(searchParams);
    next.delete('create');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);
}
