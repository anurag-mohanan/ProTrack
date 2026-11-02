import { useMemo } from 'react';
import { Autocomplete, TextField } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchPredictions, predictiveQueryKeys } from '../../api/predictive';

function useForecastProjects() {
  const delivery = useQuery({
    queryKey: predictiveQueryKeys.list('project_delivery'),
    queryFn: () => fetchPredictions({ prediction_type: 'project_delivery' }),
  });
  const hours = useQuery({
    queryKey: predictiveQueryKeys.list('project_final_hours'),
    queryFn: () => fetchPredictions({ prediction_type: 'project_final_hours' }),
  });
  const options = useMemo(() => {
    const byId = new Map<string, string>();
    for (const r of [...(delivery.data?.predictions ?? []), ...(hours.data?.predictions ?? [])]) {
      if (r.project_id && !byId.has(r.project_id)) byId.set(r.project_id, r.subject_label);
    }
    return [...byId.entries()].map(([id, label]) => ({ id, label })).sort((a, b) => a.label.localeCompare(b.label));
  }, [delivery.data, hours.data]);
  return { options, loading: delivery.isLoading || hours.isLoading };
}

/** Open projects in the caller's scope that appear in the latest prediction run. */
export function ProjectPicker({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (projectId: string | null) => void;
}) {
  const { options, loading } = useForecastProjects();
  const selected = options.find((o) => o.id === value) ?? null;
  return (
    <Autocomplete
      size="small"
      options={options}
      loading={loading}
      value={selected}
      onChange={(_, next) => onChange(next?.id ?? null)}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      renderInput={(params) => <TextField {...params} label="Open project" placeholder="Search by tool number or description" />}
      sx={{ maxWidth: 520, mb: 2 }}
      noOptionsText="No open project in your scope has been through a prediction run"
    />
  );
}
