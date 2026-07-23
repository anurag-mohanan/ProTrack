import { useCallback, useEffect, useState } from 'react';
import { useQuery, type QueryKey, type UseQueryResult } from '@tanstack/react-query';

type GeneratedReportResult<T> = UseQueryResult<T, Error> & {
  generate: () => void;
  /** True after Generate for the current filters (even while loading). */
  generationRequested: boolean;
  /** True when preview data is available for the current filters. */
  hasGenerated: boolean;
  /** True when Excel download may use the current generated preview. */
  canDownload: boolean;
};

/**
 * Report previews stay idle until the user clicks Generate.
 * Changing filters clears the generated state and disables download.
 */
export function useGeneratedReportQuery<T>(options: {
  queryKey: QueryKey;
  queryFn: () => Promise<T>;
  /** Prerequisites (e.g. customer selected). Defaults to true. */
  ready?: boolean;
}): GeneratedReportResult<T> {
  const ready = options.ready !== false;
  const optionsKey = JSON.stringify(options.queryKey);
  const [generationToken, setGenerationToken] = useState(0);
  const [boundKey, setBoundKey] = useState<string | null>(null);

  useEffect(() => {
    if (boundKey !== null && boundKey !== optionsKey) {
      setBoundKey(null);
      setGenerationToken(0);
    }
  }, [boundKey, optionsKey]);

  const generationRequested = ready && boundKey === optionsKey && generationToken > 0;

  const query = useQuery<T, Error>({
    queryKey: [...options.queryKey, 'generated', generationToken],
    queryFn: options.queryFn,
    enabled: generationRequested,
    staleTime: Infinity,
  });

  const generate = useCallback(() => {
    if (!ready) return;
    setBoundKey(optionsKey);
    setGenerationToken((token) => token + 1);
  }, [optionsKey, ready]);

  const hasGenerated = generationRequested && Boolean(query.data) && !query.isError;
  const canDownload = hasGenerated && !query.isFetching;

  return {
    ...query,
    generate,
    generationRequested,
    hasGenerated,
    canDownload,
  };
}
