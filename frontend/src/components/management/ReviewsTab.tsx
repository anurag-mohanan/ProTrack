import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import {
  commentOn,
  compareReview,
  createReview,
  fetchReview,
  fetchReviews,
  finaliseReview,
  managementQueryKeys,
  recordReviewDecision,
  regenerateReview,
  updateReview,
} from '../../api/management';
import { useToast } from '../../context/ToastContext';
import type { CockpitFilterValues, ManagementCan, ReviewSection } from '../../types/Management';
import { formatDate, formatDateTime } from '../../utils/format';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { statusLabel, valueText } from './managementFormat';
import {
  DataTable,
  ExportButton,
  HiddenSection,
  KindChip,
  MetricGrid,
  NotesList,
  SectionHeader,
  StatusChip,
} from './ManagementParts';

function Section({ title, section }: { title: string; section: ReviewSection | undefined }) {
  if (!section) return null;
  if (section.visible === false) return <HiddenSection title={title} reason={section.reason ?? 'Restricted.'} />;
  return (
    <>
      <SectionHeader title={title} />
      <MetricGrid metrics={section.kpis ?? []} />
      <NotesList notes={section.notes ?? section.limitations ?? []} />
    </>
  );
}

function ReviewDetailView({ id, can, onBack }: { id: string; can: ManagementCan; onBack: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: managementQueryKeys.review(id), queryFn: () => fetchReview(id) });
  const comparison = useQuery({ queryKey: managementQueryKeys.compare(id), queryFn: () => compareReview(id) });
  const users = useQuery({ queryKey: ['lookups', 'users'], queryFn: () => fetchUsers(), enabled: can.manage_strategy });
  const [summary, setSummary] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [decision, setDecision] = useState({ text: '', action_title: '', action_owner_id: '', action_due_date: '' });
  const refresh = (message: string) => {
    toast.showSuccess(message);
    void queryClient.invalidateQueries({ queryKey: managementQueryKeys.all });
  };
  const onError = (e: unknown) => toast.showError(getErrorMessage(e));
  const save = useMutation({ mutationFn: () => updateReview(id, { executive_summary: summary }), onSuccess: () => refresh('Summary saved.'), onError });
  const regenerate = useMutation({ mutationFn: () => regenerateReview(id), onSuccess: () => refresh('Figures regenerated.'), onError });
  const finalise = useMutation({ mutationFn: () => finaliseReview(id), onSuccess: () => refresh('Review finalised. Its figures are now fixed.'), onError });
  const decide = useMutation({
    mutationFn: () =>
      recordReviewDecision(id, {
        text: decision.text,
        action_title: decision.action_title || null,
        action_owner_id: decision.action_owner_id || null,
        action_due_date: decision.action_due_date || null,
      }),
    onSuccess: () => {
      setDecision({ text: '', action_title: '', action_owner_id: '', action_due_date: '' });
      refresh('Decision recorded.');
    },
    onError,
  });
  const addComment = useMutation({
    mutationFn: () => commentOn('reviews', id, comment.trim()),
    onSuccess: () => {
      setComment('');
      refresh('Comment added.');
    },
    onError,
  });
  if (query.isLoading) return <LoadingState message="Loading review…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const r = query.data;
  if (!r) return null;
  const snap = r.snapshot;
  return (
    <Box>
      <Button size="small" startIcon={<ArrowBackRoundedIcon />} onClick={onBack} sx={{ mb: 1 }}>
        All reviews
      </Button>
      <SectionHeader
        title={r.title}
        subtitle={`${formatDate(r.period.start)} – ${formatDate(r.period.end)} · Generated ${formatDateTime(r.generated_at)} by ${r.generated_by ?? '—'}${
          r.finalised_at ? ` · Finalised ${formatDateTime(r.finalised_at)} by ${r.finalised_by}` : ''
        }`}
        action={
          <Stack direction="row" spacing={1}>
            <StatusChip status={r.status} />
            {can.export ? <ExportButton report="review" filters={{}} extra={{ review_id: r.id }} /> : null}
            {r.can_edit ? (
              <Button size="small" variant="outlined" onClick={() => regenerate.mutate()} disabled={regenerate.isPending}>
                Regenerate figures
              </Button>
            ) : null}
            {r.can_finalise ? (
              <Button size="small" variant="contained" onClick={() => finalise.mutate()} disabled={finalise.isPending || !r.executive_summary}>
                Finalise
              </Button>
            ) : null}
          </Stack>
        }
      />

      <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Executive summary (written by a person)
        </Typography>
        {r.can_edit ? (
          <Stack spacing={1} sx={{ mt: 1 }}>
            <TextField
              multiline
              minRows={3}
              value={summary ?? r.executive_summary ?? ''}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Summarise the period. Generated highlights below are a starting point, not the official summary."
            />
            <Box>
              <Button size="small" variant="outlined" onClick={() => save.mutate()} disabled={summary === null || save.isPending}>
                Save summary
              </Button>
            </Box>
          </Stack>
        ) : (
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {r.executive_summary ?? 'Not written yet.'}
          </Typography>
        )}
        <NotesList title="Generated highlights" notes={snap.executive_summary.generated_highlights} />
        <Typography variant="caption" color="text.secondary">
          {snap.executive_summary.note}
        </Typography>
      </Paper>

      <Section title="Financial performance" section={snap.financial} />
      <Section title="Delivery performance" section={snap.delivery} />
      <Section title="Engineering efficiency" section={snap.efficiency} />
      <Section title="Workforce and capacity" section={snap.workforce} />

      <SectionHeader title="Objectives" />
      <DataTable
        rows={snap.objectives}
        rowKey={(o) => o.id}
        empty="No objectives for this period."
        columns={[
          { label: 'Objective', render: (o) => o.title },
          { label: 'Owner', render: (o) => o.owner ?? '—' },
          { label: 'Status', render: (o) => <StatusChip status={o.status} /> },
          { label: 'Progress', align: 'right', render: (o) => (o.restricted ? 'Restricted' : valueText(o.progress_percent, 'percentage')) },
        ]}
      />

      <SectionHeader title="Risks and decisions required" />
      <NotesList title="Top risks" notes={snap.risks.top.map((x) => `${x.project}: ${x.title} (${x.severity})`)} />
      <NotesList title="Decisions required" notes={snap.decisions_required.map((d) => d.text)} />

      <SectionHeader title="Forecasts (not actuals)" subtitle={snap.forecasts.note} />
      <Typography variant="body2" sx={{ mb: 2 }}>
        <KindChip kind="forecast" /> Projects with forecast risk: {snap.forecasts.projects_forecast_risk ?? '—'} · Stored predictions:{' '}
        {Object.entries(snap.forecasts.stored_predictions)
          .map(([k, v]) => `${statusLabel(k)} ${v}`)
          .join(', ') || 'none'}
      </Typography>

      <SectionHeader title="Comparison with the previous review" subtitle={comparison.data?.note} />
      <DataTable
        rows={comparison.data?.rows ?? []}
        rowKey={(row) => row.key}
        empty="No earlier review to compare with."
        columns={[
          { label: 'Measure', render: (row) => row.label },
          { label: 'This review', align: 'right', render: (row) => valueText(row.current, row.unit) },
          { label: comparison.data?.other?.title ?? 'Previous', align: 'right', render: (row) => valueText(row.previous, row.unit) },
          { label: 'Change', align: 'right', render: (row) => valueText(row.change, row.unit) },
        ]}
      />

      <SectionHeader title="Decisions and actions" />
      <DataTable
        rows={r.decisions}
        rowKey={(d) => d.id}
        empty="No decisions recorded."
        columns={[
          { label: 'Decision', render: (d) => d.body ?? d.summary },
          { label: 'By', render: (d) => d.actor ?? '—' },
          { label: 'When', render: (d) => formatDateTime(d.created_at) },
        ]}
      />
      <DataTable
        rows={r.actions}
        rowKey={(a) => a.id}
        empty="No actions from this review."
        columns={[
          { label: 'Action', render: (a) => a.title },
          { label: 'Owner', render: (a) => a.owner ?? '—' },
          { label: 'Due', render: (a) => (a.due_date ? formatDate(a.due_date) : '—') },
          { label: 'Status', render: (a) => <StatusChip status={a.status} /> },
        ]}
      />
      <SectionHeader title="Discussion" />
      <DataTable
        rows={r.events.filter((e) => e.event_type === 'comment')}
        rowKey={(e) => e.id}
        empty="No comments yet."
        columns={[
          { label: 'Comment', render: (e) => e.body ?? e.summary },
          { label: 'By', render: (e) => e.actor ?? '—' },
          { label: 'When', render: (e) => formatDateTime(e.created_at) },
        ]}
      />
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <TextField size="small" label="Add a comment" value={comment} onChange={(e) => setComment(e.target.value)} fullWidth />
        <Button variant="outlined" onClick={() => addComment.mutate()} disabled={comment.trim().length < 2 || addComment.isPending}>
          Add
        </Button>
      </Stack>
      {can.manage_strategy ? (
        <Paper variant="outlined" sx={{ p: 1.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
            Record a decision
          </Typography>
          <Stack spacing={1}>
            <TextField size="small" label="Decision" value={decision.text} onChange={(e) => setDecision({ ...decision, text: e.target.value })} />
            <Stack direction="row" spacing={1}>
              <TextField size="small" label="Follow-up action (optional)" value={decision.action_title} onChange={(e) => setDecision({ ...decision, action_title: e.target.value })} fullWidth />
              <TextField select size="small" label="Owner" value={decision.action_owner_id} onChange={(e) => setDecision({ ...decision, action_owner_id: e.target.value })} sx={{ minWidth: 180 }}>
                <MenuItem value="">—</MenuItem>
                {(users.data ?? []).map((u) => (
                  <MenuItem key={u.id} value={u.id}>
                    {`${u.first_name ?? ''} ${u.last_name ?? ''}`.trim() || u.email}
                  </MenuItem>
                ))}
              </TextField>
              <TextField size="small" type="date" label="Due" slotProps={{ inputLabel: { shrink: true } }} value={decision.action_due_date} onChange={(e) => setDecision({ ...decision, action_due_date: e.target.value })} />
            </Stack>
            <Box>
              <Button
                size="small"
                variant="contained"
                onClick={() => decide.mutate()}
                disabled={decision.text.length < 3 || (Boolean(decision.action_title) && !decision.action_owner_id) || decide.isPending}
              >
                Record decision
              </Button>
            </Box>
          </Stack>
        </Paper>
      ) : null}
    </Box>
  );
}

export function ReviewsTab({ can, fy }: { filters: CockpitFilterValues; can: ManagementCan; fy: number }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [openId, setOpenId] = useState<string | null>(null);
  const [form, setForm] = useState<{ review_type: 'monthly' | 'quarterly' | 'annual'; period_index: number }>({
    review_type: 'monthly',
    period_index: 1,
  });
  const query = useQuery({ queryKey: managementQueryKeys.reviews, queryFn: fetchReviews, enabled: can.reviews });
  const create = useMutation({
    mutationFn: () =>
      createReview({ review_type: form.review_type, fy_start_year: fy, period_index: form.review_type === 'annual' ? null : form.period_index }),
    onSuccess: (r) => {
      toast.showSuccess('Review generated as a draft.');
      void queryClient.invalidateQueries({ queryKey: managementQueryKeys.reviews });
      setOpenId(r.id);
    },
    onError: (e) => toast.showError(getErrorMessage(e)),
  });
  if (!can.reviews) {
    return <Alert severity="info">Management reviews need organisation-wide report scope or the Manage strategy permission.</Alert>;
  }
  if (openId) return <ReviewDetailView id={openId} can={can} onBack={() => setOpenId(null)} />;
  if (query.isLoading) return <LoadingState message="Loading reviews…" />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  return (
    <Box>
      <SectionHeader
        title="Management reviews"
        subtitle="Generated from current figures as a draft; once finalised by an approver, the figures are fixed."
        action={
          can.manage_strategy ? (
            <Stack direction="row" spacing={1}>
              <TextField
                select
                size="small"
                label="Type"
                value={form.review_type}
                onChange={(e) => setForm({ ...form, review_type: e.target.value as typeof form.review_type })}
              >
                <MenuItem value="monthly">Monthly</MenuItem>
                <MenuItem value="quarterly">Quarterly</MenuItem>
                <MenuItem value="annual">Annual</MenuItem>
              </TextField>
              {form.review_type !== 'annual' ? (
                <TextField
                  size="small"
                  type="number"
                  label={form.review_type === 'monthly' ? 'Month of FY' : 'Quarter'}
                  value={form.period_index}
                  onChange={(e) => setForm({ ...form, period_index: Number(e.target.value) })}
                  sx={{ width: 120 }}
                />
              ) : null}
              <Button size="small" variant="contained" onClick={() => create.mutate()} disabled={create.isPending}>
                Generate
              </Button>
            </Stack>
          ) : null
        }
      />
      <DataTable
        rows={query.data ?? []}
        rowKey={(r) => r.id}
        onRowClick={(r) => setOpenId(r.id)}
        empty="No reviews yet."
        columns={[
          { label: 'Review', render: (r) => r.title },
          { label: 'Period', render: (r) => `${formatDate(r.period.start)} – ${formatDate(r.period.end)}` },
          { label: 'Status', render: (r) => <StatusChip status={r.status} /> },
          { label: 'Generated', render: (r) => formatDateTime(r.generated_at) },
          { label: 'Finalised by', render: (r) => r.finalised_by ?? '—' },
        ]}
      />
    </Box>
  );
}
