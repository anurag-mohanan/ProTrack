import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Chip,
  Grid,
  Typography,
} from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { fetchSystemHealth } from '../../api/system';
import {
  PRODUCT_NAME,
  RELEASE_LABEL,
  VERSION_DISPLAY,
} from '../../config/appMeta';
import { formatDisplayValue } from '../../utils/format';

function StatusChip({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const color =
    normalized === 'ok' ? 'success' : normalized === 'degraded' ? 'warning' : 'error';
  return <Chip label={formatDisplayValue(value)} size="small" color={color} />;
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <ContentCard title={label}>
      <Typography variant="h6">{formatDisplayValue(value)}</Typography>
    </ContentCard>
  );
}

export default function AdminSystemPage() {
  const healthQuery = useQuery({
    queryKey: ['system-health'],
    queryFn: fetchSystemHealth,
  });

  if (healthQuery.isLoading) {
    return <LoadingState message="Loading system health…" />;
  }

  if (healthQuery.isError || !healthQuery.data) {
    return (
      <Box>
        <PageHeader title="System Health" subtitle="Platform runtime and maintenance status" />
        <Alert severity="error">Unable to load system health information.</Alert>
      </Box>
    );
  }

  const health = healthQuery.data;

  return (
    <Box>
      <PageHeader
        title="System Health"
        subtitle="Release information, services, and platform maintenance"
      />

      <Box sx={{ mb: 3 }}>
        <ContentCard title="Release Information">
          <Typography variant="body1" sx={{ fontWeight: 700, mb: 0.5 }}>
            {PRODUCT_NAME} {VERSION_DISPLAY}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {RELEASE_LABEL}
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <Chip
              label={`API ${health.application_version} ${health.release_candidate}`}
              size="small"
              variant="outlined"
            />
            {health.internal_release ? (
              <Chip label="Internal Release Mode" size="small" color="info" variant="outlined" />
            ) : null}
          </Box>
        </ContentCard>
      </Box>

      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <ContentCard title="Service Status">
            <Box sx={{ display: 'grid', gap: 1.25 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="body2">Backend</Typography>
                <StatusChip value={health.backend_status} />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="body2">Database</Typography>
                <StatusChip value={health.database_status} />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="body2">API</Typography>
                <StatusChip value={health.api_status} />
              </Box>
            </Box>
          </ContentCard>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <MetricCard label="Active Users" value={health.active_users} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <MetricCard label="Storage Usage" value={health.storage_usage_label} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <MetricCard label="Database Version" value={health.database_version ?? '—'} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <MetricCard label="Import Queue" value={health.import_queue} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <MetricCard label="Failed Jobs" value={health.failed_jobs} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <MetricCard label="Last Backup" value={health.last_backup ? 'Scheduled' : '—'} />
        </Grid>
      </Grid>

      <ContentCard title="Recent Errors">
        {health.recent_errors.length ? (
          <Box sx={{ display: 'grid', gap: 1 }}>
            {health.recent_errors.map((entry) => (
              <Typography key={entry} variant="body2" color="text.secondary">
                {formatDisplayValue(entry)}
              </Typography>
            ))}
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No recent errors recorded.
          </Typography>
        )}
      </ContentCard>
    </Box>
  );
}
