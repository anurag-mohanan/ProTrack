import { Box, Stack, Typography } from '@mui/material';
import type { CollaborationActivityDashboard } from '../../types/Dashboard';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { formatNumber } from '../../utils/format';

interface CollaborationActivityWidgetProps {
  data: CollaborationActivityDashboard | null | undefined;
  /** Denser layout for the dashboard right rail. */
  compact?: boolean;
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <Typography variant="body2" color="text.secondary">
      {label}: <strong>{value}</strong>
    </Typography>
  );
}

export function CollaborationActivityWidget({
  data,
  compact = false,
}: CollaborationActivityWidgetProps) {
  if (!data) {
    return (
      <DashboardPanel title="Collaboration Activity" subtitle="Cross-project support and peer review">
        <Typography variant="body2" color="text.secondary">
          Collaboration metrics are not available right now.
        </Typography>
      </DashboardPanel>
    );
  }

  const hasContent =
    data.most_assisted_projects.length > 0 ||
    data.designers_receiving_support.length > 0 ||
    data.designers_providing_support.length > 0 ||
    data.peer_review_hours_this_month > 0;

  if (!hasContent) {
    return (
      <DashboardPanel title="Collaboration Activity" subtitle="Cross-project support and peer review">
        <Typography variant="body2" color="text.secondary">
          No collaboration hours logged this month yet.
        </Typography>
      </DashboardPanel>
    );
  }

  return (
    <DashboardPanel
      title="Collaboration Activity"
      subtitle={
        compact
          ? 'Support & peer review'
          : 'Support, peer review, and multi-contributor projects'
      }
    >
      <Stack spacing={compact ? 1 : 1.5}>
        <MetricLine
          label="Multi-contributor projects"
          value={String(data.multi_contributor_projects)}
        />
        <MetricLine
          label="Peer review hours (month)"
          value={`${formatNumber(data.peer_review_hours_this_month, 1)}h`}
        />
        <MetricLine
          label="Cross-team collaborations"
          value={String(data.cross_team_collaboration_count)}
        />

        {!compact && data.most_assisted_projects.length ? (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
              Most assisted projects
            </Typography>
            {data.most_assisted_projects.map((row) => (
              <Typography key={row.project_id} variant="body2" color="text.secondary">
                {row.tool_number}
                {row.customer_name ? ` · ${row.customer_name}` : ''} —{' '}
                {formatNumber(row.support_hours, 1)}h support · {row.contributor_count} contributors
              </Typography>
            ))}
          </Box>
        ) : null}

        {!compact && data.designers_receiving_support.length ? (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
              Designers receiving support
            </Typography>
            {data.designers_receiving_support.map((row) => (
              <Typography key={row.user_id} variant="body2" color="text.secondary">
                {row.user_name} — {formatNumber(row.hours_received ?? 0, 1)}h
              </Typography>
            ))}
          </Box>
        ) : null}

        {!compact && data.designers_providing_support.length ? (
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
              Designers providing support
            </Typography>
            {data.designers_providing_support.map((row) => (
              <Typography key={row.user_id} variant="body2" color="text.secondary">
                {row.user_name} — {formatNumber(row.hours_provided ?? 0, 1)}h
              </Typography>
            ))}
          </Box>
        ) : null}
      </Stack>
    </DashboardPanel>
  );
}
