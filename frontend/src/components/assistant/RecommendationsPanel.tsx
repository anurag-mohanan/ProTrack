import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  MenuItem,
  Pagination,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import {
  assistantQueryKeys,
  decideRecommendation,
  fetchRecommendations,
  type AssistantRecommendation,
  type RecommendationStatus,
} from '../../api/assistant';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { formatDateTime } from '../../utils/format';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';

const PAGE_SIZE = 20;

const STATUS_LABEL: Record<RecommendationStatus, string> = {
  new: 'New',
  accepted: 'Accepted',
  rejected: 'Rejected',
  deferred: 'Deferred',
  completed: 'Completed',
};

const STATUS_COLOR: Record<RecommendationStatus, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
  new: 'info',
  accepted: 'success',
  rejected: 'default',
  deferred: 'warning',
  completed: 'success',
};

const ACTION_LABEL: Record<Exclude<RecommendationStatus, 'new'>, string> = {
  accepted: 'Accept',
  rejected: 'Reject',
  deferred: 'Defer',
  completed: 'Mark completed',
};

type Decision = { rec: AssistantRecommendation; status: Exclude<RecommendationStatus, 'new'> };

function RecommendationCard({ rec, onDecide }: { rec: AssistantRecommendation; onDecide: (d: Decision) => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
        <Typography variant="subtitle2" sx={{ flex: 1, minWidth: 200 }}>
          {rec.title}
        </Typography>
        <Chip size="small" label={`${rec.priority} priority`} variant="outlined" />
        <Chip size="small" label={STATUS_LABEL[rec.status]} color={STATUS_COLOR[rec.status]} />
      </Box>
      <Typography variant="caption" color="text.secondary">
        {rec.category.replace(/_/g, ' ')}
        {rec.project_label ? ` · ${rec.project_label}` : ''} · raised {formatDateTime(rec.created_at)}
        {rec.created_by ? ` by ${rec.created_by}'s assistant` : ''}
      </Typography>
      <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
        {rec.description}
      </Typography>
      {rec.suggested_action ? (
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>Suggested action:</strong> {rec.suggested_action}
          {rec.suggested_owner ? ` (suggested owner: ${rec.suggested_owner})` : ''}
        </Typography>
      ) : null}
      {rec.evidence.length ? (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
            Evidence
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
            {rec.evidence.map((source) =>
              source.route ? (
                <Chip
                  key={source.key}
                  size="small"
                  variant="outlined"
                  clickable
                  component={RouterLink}
                  to={source.route}
                  label={source.label}
                />
              ) : (
                <Chip key={source.key} size="small" variant="outlined" label={source.label} />
              ),
            )}
          </Box>
        </Box>
      ) : null}
      {rec.decided_by || rec.completed_by || rec.resolution_notes ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          {rec.decided_by ? `Decided by ${rec.decided_by} on ${formatDateTime(rec.decided_at)}. ` : ''}
          {rec.completed_by ? `Completed by ${rec.completed_by} on ${formatDateTime(rec.completed_at)}. ` : ''}
          {rec.resolution_notes ? `Notes: ${rec.resolution_notes}` : ''}
        </Typography>
      ) : null}
      <Box sx={{ display: 'flex', gap: 1, mt: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
        {rec.allowed_transitions.map((status) => (
          <Button
            key={status}
            size="small"
            variant={status === 'accepted' || status === 'completed' ? 'contained' : 'outlined'}
            color={status === 'rejected' ? 'inherit' : 'primary'}
            onClick={() => onDecide({ rec, status })}
          >
            {ACTION_LABEL[status]}
          </Button>
        ))}
        {rec.workflow_route ? (
          <Link component={RouterLink} to={rec.workflow_route} variant="body2" sx={{ ml: 'auto' }}>
            Open the related workflow
          </Link>
        ) : null}
      </Box>
    </Paper>
  );
}

export function RecommendationsPanel() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState<RecommendationStatus | ''>('');
  const [page, setPage] = useState(1);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [note, setNote] = useState('');

  const query = useQuery({
    queryKey: assistantQueryKeys.recommendations(status || undefined, page),
    queryFn: () => fetchRecommendations({ status: status || undefined, page, page_size: PAGE_SIZE }),
  });

  const mutation = useMutation({
    mutationFn: (d: Decision & { note: string }) => decideRecommendation(d.rec.id, d.status, d.note),
    onSuccess: async (rec) => {
      toast.showSuccess(`Recommendation ${STATUS_LABEL[rec.status].toLowerCase()}. Nothing else in ProTrack was changed.`);
      setDecision(null);
      setNote('');
      await queryClient.invalidateQueries({ queryKey: ['assistant'] });
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  const totalPages = query.data ? Math.max(1, Math.ceil(query.data.total / PAGE_SIZE)) : 1;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1, minWidth: 260 }}>
          Recommendations the assistant recorded for review. Accepting one does not change any project, assignment or
          financial record; carry out the action in the related workflow.
        </Typography>
        <TextField
          select
          size="small"
          label="Status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as RecommendationStatus | '');
            setPage(1);
          }}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">All</MenuItem>
          {(Object.keys(STATUS_LABEL) as RecommendationStatus[]).map((s) => (
            <MenuItem key={s} value={s}>
              {STATUS_LABEL[s]}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      {query.isLoading ? <LoadingState message="Loading recommendations…" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data && !query.data.items.length ? (
        <EmptyState
          title="No recommendations"
          description="When the assistant identifies an action backed by ProTrack data, it records it here for a decision."
        />
      ) : null}
      <Stack sx={{ gap: 1.5 }}>
        {query.data?.items.map((rec) => <RecommendationCard key={rec.id} rec={rec} onDecide={setDecision} />)}
      </Stack>
      {totalPages > 1 ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} size="small" />
        </Box>
      ) : null}

      <Dialog open={decision !== null} onClose={() => !mutation.isPending && setDecision(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{decision ? `${ACTION_LABEL[decision.status]}: ${decision.rec.title}` : ''}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Your decision and note are recorded in the decision audit with your name and the time.
          </Typography>
          <TextField
            label="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            multiline
            minRows={2}
            fullWidth
            slotProps={{ htmlInput: { maxLength: 2000 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDecision(null)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={mutation.isPending}
            onClick={() => decision && mutation.mutate({ ...decision, note })}
          >
            {decision ? ACTION_LABEL[decision.status] : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
