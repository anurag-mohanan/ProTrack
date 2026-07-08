import { Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchQuoteRecommendation, aiQueryKeys } from '../../api/ai';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { formatNumber } from '../../utils/format';

interface QuoteAssistantPanelProps {
  projectId: string;
}

export function QuoteAssistantPanel({ projectId }: QuoteAssistantPanelProps) {
  const query = useQuery({
    queryKey: aiQueryKeys.quote(projectId),
    queryFn: () => fetchQuoteRecommendation(projectId),
    enabled: Boolean(projectId),
  });

  if (query.isLoading) return <LoadingState message="Analyzing similar projects..." />;
  if (query.error) return <ErrorState error={query.error} title="Quote analysis unavailable" />;
  if (!query.data) return null;

  const quote = query.data;
  const s = quote.suggested;

  return (
    <DashboardPanel
      title="AI Quoting Assistant"
      subtitle={quote.rationale ?? 'Historical comparison from completed projects'}
    >
      <Stack spacing={1}>
        <Typography variant="body2">
          <strong>Suggested Quote</strong>
        </Typography>
        <Typography variant="body2">Design: {formatNumber(s.design_hours, 1)} hrs</Typography>
        <Typography variant="body2">Surfacing: {formatNumber(s.surfacing_hours, 1)} hrs</Typography>
        <Typography variant="body2">Checking: {formatNumber(s.checking_hours, 1)} hrs</Typography>
        <Typography variant="body2">BOM: {formatNumber(s.bom_hours, 1)} hrs</Typography>
        <Typography variant="subtitle2" sx={{ fontWeight: 800, mt: 0.5 }}>
          Total: {formatNumber(s.total_hours, 1)} hrs — Confidence: {Math.round(quote.confidence_percent)}%
        </Typography>
        {quote.similar_projects.length ? (
          <Typography variant="caption" color="text.secondary">
            Based on: {quote.similar_projects.map((p) => p.tool_number).join(', ')}
          </Typography>
        ) : null}
      </Stack>
    </DashboardPanel>
  );
}
