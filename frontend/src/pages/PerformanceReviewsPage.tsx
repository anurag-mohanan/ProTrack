import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Chip,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import StarOutlineOutlinedIcon from '@mui/icons-material/StarOutlineOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, getErrorMessage } from '../api/client';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { FinanceSection } from '../components/finance/FinanceCockpitPrimitives';
import { KpiMetricCard } from '../components/ui/design-system/KpiMetricCard';
import {
  FALLBACK_RATING_SCALE,
  formatScore,
  statusChipColor,
  type RatingScaleItem,
} from '../components/performanceReview/performanceReviewConstants';
import { PerformanceReviewHero } from '../components/performanceReview/PerformanceReviewPrimitives';
import { type ReviewProjectRow } from '../components/performanceReview/PerformanceReviewProjectsPanel';
import { PerformanceReviewFormDocument } from '../components/performanceReview/PerformanceReviewFormDocument';
import {
  currentReviewYear,
  defaultPeriodLabel,
  reviewPeriodBounds,
} from '../components/performanceReview/performanceReviewPeriod';
import { DeleteDialog } from '../components/ui/design-system/DeleteDialog';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

type ReviewItem = {
  id?: string;
  prompt: string;
  guidance?: string | null;
  rating?: number | string | null;
  rating_label?: string | null;
  employee_comment?: string | null;
  manager_comment?: string | null;
  sort_order: number;
};

type ReviewSection = {
  id?: string;
  title: string;
  description?: string | null;
  employee_notes?: string | null;
  reviewer_notes?: string | null;
  employee_notes_label?: string | null;
  average_score?: number | string | null;
  rated_count?: number;
  total_count?: number;
  sort_order: number;
  items: ReviewItem[];
};

type Review = {
  id: string;
  employee_id: string;
  employee_name: string;
  employee_department?: string | null;
  employee_designation?: string | null;
  employee_role?: string | null;
  employee_joining_date?: string | null;
  employee_first_job_date?: string | null;
  company_experience?: string | null;
  reviewer_id: string;
  reviewer_name: string;
  team_id?: string | null;
  team_name?: string | null;
  cycle_id?: string | null;
  cycle_title?: string | null;
  period_label: string;
  status: string;
  review_date?: string | null;
  due_date?: string | null;
  total_experience?: string | null;
  industry_experience?: string | null;
  overall_score?: number | string | null;
  overall_score_label?: string | null;
  completion_percent?: number;
  employee_summary?: string | null;
  manager_summary?: string | null;
  strengths_summary?: string | null;
  improvement_summary?: string | null;
  career_goals?: string | null;
  submitted_at?: string | null;
  acknowledged_at?: string | null;
  sections: ReviewSection[];
  projects?: ReviewProjectRow[];
  review_period_start?: string | null;
  review_period_end?: string | null;
  is_editable: boolean;
  can_acknowledge: boolean;
};

type TeamMember = {
  user_id: string;
  name: string;
  email: string;
  team_id: string;
  team_name: string;
  review_count: number;
};

type ReviewCycle = {
  id: string;
  title: string;
  review_year: number;
  due_date?: string | null;
  status: string;
};

type ReviewTemplate = {
  form_code: string;
  form_title: string;
  form_revision?: string;
  review_cycle_month?: number;
  review_cycle_note?: string;
  rating_scale: RatingScaleItem[];
};

type EditorState = {
  period_label: string;
  review_date: string;
  due_date: string;
  total_experience: string;
  industry_experience: string;
  overall_score: string;
  employee_summary: string;
  manager_summary: string;
  strengths_summary: string;
  improvement_summary: string;
  career_goals: string;
  sections: ReviewSection[];
  projects: ReviewProjectRow[];
};

function cloneSections(sections: ReviewSection[]): ReviewSection[] {
  return sections.map((section) => ({
    ...section,
    items: section.items.map((item) => ({ ...item })),
  }));
}

function reviewToEditor(review: Review): EditorState {
  return {
    period_label: review.period_label ?? '',
    review_date: review.review_date ?? '',
    due_date: review.due_date ?? '',
    total_experience: review.total_experience ?? review.company_experience ?? '',
    industry_experience: review.industry_experience ?? '',
    overall_score:
      review.overall_score === null || review.overall_score === undefined
        ? ''
        : String(review.overall_score),
    employee_summary: review.employee_summary ?? '',
    manager_summary: review.manager_summary ?? '',
    strengths_summary: review.strengths_summary ?? '',
    improvement_summary: review.improvement_summary ?? '',
    career_goals: review.career_goals ?? '',
    sections: cloneSections(review.sections ?? []),
    projects: (review.projects ?? []).map((row) => ({ ...row })),
  };
}

export function PerformanceReviewsPage({ embedded = false }: { embedded?: boolean }) {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [selectedReviewId, setSelectedReviewId] = useState<string>('');
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [selectedCycleId, setSelectedCycleId] = useState('');
  const [periodLabel, setPeriodLabel] = useState(defaultPeriodLabel());
  const [reviewYear, setReviewYear] = useState(currentReviewYear());
  const [dueDate, setDueDate] = useState('');
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Review | null>(null);

  const templateQuery = useQuery({
    queryKey: ['performance-reviews', 'template'],
    queryFn: async () => (await apiClient.get<ReviewTemplate>('/hr/reviews/template')).data,
  });

  const ratingScale = templateQuery.data?.rating_scale ?? FALLBACK_RATING_SCALE;

  const myReviewsQuery = useQuery({
    queryKey: ['performance-reviews', 'me'],
    queryFn: async () => (await apiClient.get<Review[]>('/hr/reviews/me')).data,
  });

  const teamMembersQuery = useQuery({
    queryKey: ['performance-reviews', 'team-members'],
    queryFn: async () => (await apiClient.get<TeamMember[]>('/hr/reviews/team-members')).data,
  });

  const cyclesQuery = useQuery({
    queryKey: ['performance-reviews', 'cycles'],
    queryFn: async () => (await apiClient.get<ReviewCycle[]>('/hr/review-cycles')).data,
  });

  const teamReviewsQuery = useQuery({
    queryKey: ['performance-reviews', 'team', selectedTeamId || 'all'],
    queryFn: async () => {
      const query = selectedTeamId ? `?team_id=${selectedTeamId}` : '';
      return (await apiClient.get<Review[]>(`/hr/reviews/team${query}`)).data;
    },
    enabled: (teamMembersQuery.data?.length ?? 0) > 0,
  });

  const createReviewMutation = useMutation({
    mutationFn: async () => {
      const member = (teamMembersQuery.data ?? []).find((row) => row.user_id === selectedMemberId);
      const teamIdForCreate = selectedTeamId || member?.team_id || '';
      if (!selectedMemberId || !teamIdForCreate) {
        throw new Error('Select a team member to create a review.');
      }
      return (
        await apiClient.post<Review>('/hr/reviews', {
          employee_id: selectedMemberId,
          reviewer_id: user?.id,
          team_id: teamIdForCreate,
          cycle_id: selectedCycleId || null,
          period_label: periodLabel || defaultPeriodLabel(reviewYear),
          review_year: reviewYear,
          due_date: dueDate || null,
        })
      ).data;
    },
    onSuccess: (review) => {
      showSuccess('Performance review sheet created');
      setSelectedReviewId(review.id);
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const updateReviewMutation = useMutation({
    mutationFn: async (payload: { id: string; body: Record<string, unknown> }) =>
      (await apiClient.patch<Review>(`/hr/reviews/${payload.id}`, payload.body)).data,
    onSuccess: (review) => {
      showSuccess('Performance review updated');
      setSelectedReviewId(review.id);
      setEditor(reviewToEditor(review));
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const deleteReviewMutation = useMutation({
    mutationFn: async (reviewId: string) => {
      await apiClient.delete(`/hr/reviews/${reviewId}`);
    },
    onSuccess: () => {
      showSuccess('Performance review deleted');
      setDeleteTarget(null);
      setSelectedReviewId('');
      setEditor(null);
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const importProjectsMutation = useMutation({
    mutationFn: async (reviewId: string) =>
      (
        await apiClient.patch<Review>(`/hr/reviews/${reviewId}`, {
          import_suggested_projects: true,
        })
      ).data,
    onSuccess: (review) => {
      showSuccess('Assigned projects imported from ProTrack');
      setEditor(reviewToEditor(review));
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const teamMembers = teamMembersQuery.data ?? [];
  const teamOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of teamMembers) {
      if (!seen.has(row.team_id)) seen.set(row.team_id, row.team_name);
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
  }, [teamMembers]);

  useEffect(() => {
    // Keep selection only when it still exists in options; default stays All teams ('').
    if (selectedTeamId && !teamOptions.some((team) => team.id === selectedTeamId)) {
      setSelectedTeamId('');
    }
  }, [selectedTeamId, teamOptions]);

  const filteredMembers = useMemo(
    () => teamMembers.filter((row) => !selectedTeamId || row.team_id === selectedTeamId),
    [selectedTeamId, teamMembers],
  );

  const selectedMember = useMemo(
    () => filteredMembers.find((row) => row.user_id === selectedMemberId) ?? null,
    [filteredMembers, selectedMemberId],
  );

  const createTeamId = selectedTeamId || selectedMember?.team_id || '';


  const currentReviews = tab === 0 ? myReviewsQuery.data ?? [] : teamReviewsQuery.data ?? [];
  const selectedReview =
    currentReviews.find((row) => row.id === selectedReviewId) ?? currentReviews[0] ?? null;

  useEffect(() => {
    if (selectedReview) {
      setSelectedReviewId(selectedReview.id);
      setEditor(reviewToEditor(selectedReview));
    } else {
      setEditor(null);
    }
  }, [selectedReview?.id]);

  if (myReviewsQuery.isLoading || teamMembersQuery.isLoading || templateQuery.isLoading) {
    return <LoadingState message="Loading performance reviews…" />;
  }

  const canManageTeamReviews = teamMembers.length > 0;
  const submittedCount = (teamReviewsQuery.data ?? []).filter((row) => row.status !== 'draft').length;

  return (
    <Stack spacing={2.5}>
      {!embedded ? (
        <PageHeader
          title="Performance Reviews"
          subtitle="PP-HRD-FO-20 aligned review workspace with competency ratings, achievements, and annual goals."
        />
      ) : null}

      <PerformanceReviewHero
        formCode={templateQuery.data?.form_code ?? 'PP-HRD-FO-20'}
        formTitle={templateQuery.data?.form_title ?? 'Employee Performance Review'}
        periodLabel={selectedReview?.period_label ?? periodLabel}
        status={selectedReview?.status}
      />

      {templateQuery.data?.review_cycle_note ? (
        <Typography variant="body2" color="text.secondary">
          {templateQuery.data.review_cycle_note}
          {templateQuery.data.form_revision ? ` · ${templateQuery.data.form_revision}` : ''}
        </Typography>
      ) : null}

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="My Reviews"
            value={String(myReviewsQuery.data?.length ?? 0)}
            subtitle="Historical review sheets"
            icon={AssessmentOutlinedIcon}
            accent="primary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Team Members"
            value={String(teamMembers.length)}
            subtitle="Eligible for team reviews"
            icon={GroupsOutlinedIcon}
            accent="info"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Submitted"
            value={String(submittedCount)}
            subtitle="Team reviews in progress"
            icon={TaskAltOutlinedIcon}
            accent="success"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <KpiMetricCard
            title="Overall Score"
            value={formatScore(selectedReview?.overall_score)}
            subtitle={selectedReview?.overall_score_label ?? 'Select a review'}
            icon={StarOutlineOutlinedIcon}
            accent="warning"
          />
        </Grid>
      </Grid>

      <Tabs value={tab} onChange={(_, value) => setTab(value)}>
        <Tab label="My Reviews" />
        {canManageTeamReviews ? <Tab label="Team Reviews" /> : null}
      </Tabs>

      {tab === 0 ? (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <ReviewListCard
              title="My review history"
              rows={(myReviewsQuery.data ?? []).map((review) => ({
                id: review.id,
                primary: review.period_label,
                secondary: review.team_name ?? 'Team',
                status: review.status,
                score: review.overall_score,
              }))}
              selectedId={selectedReviewId}
              onSelect={setSelectedReviewId}
              emptyLabel="No reviews available yet."
            />
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <ReviewDetailCard
              review={selectedReview}
              editor={editor}
              ratingScale={ratingScale}
              canManage={false}
              onChange={setEditor}
              onEmployeeSave={() => {
                if (!selectedReview || !editor) return;
                updateReviewMutation.mutate({
                  id: selectedReview.id,
                  body: {
                    employee_summary: editor.employee_summary || null,
                    career_goals: editor.career_goals || null,
                    sections: editor.sections,
                    projects: editor.projects,
                  },
                });
              }}
              onImportProjects={
                selectedReview
                  ? () => importProjectsMutation.mutate(selectedReview.id)
                  : undefined
              }
              importingProjects={importProjectsMutation.isPending}
              onAcknowledge={() =>
                selectedReview &&
                updateReviewMutation.mutate({ id: selectedReview.id, body: { acknowledged: true } })
              }
              saving={updateReviewMutation.isPending}
            />
          </Grid>
        </Grid>
      ) : null}

      {tab === 1 && canManageTeamReviews ? (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <FinanceSection title="Create team review" subtitle="Launch a new PP-HRD-FO-20 sheet">
              <Stack spacing={1.5}>
                <FormControl size="small" fullWidth>
                  <InputLabel>Team</InputLabel>
                  <Select
                    label="Team"
                    value={selectedTeamId}
                    displayEmpty
                    onChange={(e) => {
                      setSelectedTeamId(String(e.target.value));
                      setSelectedMemberId('');
                    }}
                  >
                    <MenuItem value="">All teams</MenuItem>
                    {teamOptions.map((team) => (
                      <MenuItem key={team.id} value={team.id}>
                        {team.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" fullWidth>
                  <InputLabel>Team member</InputLabel>
                  <Select
                    label="Team member"
                    value={selectedMemberId}
                    displayEmpty
                    onChange={(e) => setSelectedMemberId(String(e.target.value))}
                  >
                    <MenuItem value="">
                      <em>Select member</em>
                    </MenuItem>
                    {filteredMembers.map((member) => (
                      <MenuItem key={`${member.team_id}-${member.user_id}`} value={member.user_id}>
                        {selectedTeamId
                          ? member.name
                          : `${member.name} · ${member.team_name}`}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" fullWidth>
                  <InputLabel>Cycle</InputLabel>
                  <Select
                    label="Cycle"
                    value={selectedCycleId}
                    onChange={(e) => setSelectedCycleId(String(e.target.value))}
                  >
                    <MenuItem value="">No cycle</MenuItem>
                    {(cyclesQuery.data ?? []).map((cycle) => (
                      <MenuItem key={cycle.id} value={cycle.id}>
                        {cycle.title}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                  <TextField
                    size="small"
                    label="Period label"
                    value={periodLabel}
                    onChange={(e) => setPeriodLabel(e.target.value)}
                    helperText={`${reviewPeriodBounds(reviewYear).start} → ${reviewPeriodBounds(reviewYear).end}`}
                  />
                  <TextField
                    size="small"
                    type="number"
                    label="Review year (July cycle)"
                    value={reviewYear}
                    onChange={(e) => {
                      const nextYear = Number(e.target.value) || currentReviewYear();
                      setReviewYear(nextYear);
                      setPeriodLabel(defaultPeriodLabel(nextYear));
                    }}
                  />
                <TextField
                  size="small"
                  type="date"
                  label="Due date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <Button
                  variant="contained"
                  disabled={!createTeamId || !selectedMemberId || createReviewMutation.isPending}
                  onClick={() => createReviewMutation.mutate()}
                >
                  Create Review Sheet
                </Button>
              </Stack>
              <Divider sx={{ my: 2 }} />
              <ReviewListCard
                title="Existing team reviews"
                rows={(teamReviewsQuery.data ?? []).map((review) => ({
                  id: review.id,
                  primary: review.employee_name,
                  secondary: review.period_label,
                  status: review.status,
                  score: review.overall_score,
                }))}
                selectedId={selectedReviewId}
                onSelect={setSelectedReviewId}
                emptyLabel="No team reviews yet."
                embedded
              />
            </FinanceSection>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <ReviewDetailCard
              review={selectedReview}
              editor={editor}
              ratingScale={ratingScale}
              canManage
              onChange={setEditor}
              onSave={(status) => {
                if (!selectedReview || !editor) return;
                updateReviewMutation.mutate({
                  id: selectedReview.id,
                  body: {
                    period_label: editor.period_label,
                    review_date: editor.review_date || null,
                    due_date: editor.due_date || null,
                    total_experience: editor.total_experience || null,
                    industry_experience: editor.industry_experience || null,
                    employee_summary: editor.employee_summary || null,
                    manager_summary: editor.manager_summary || null,
                    strengths_summary: editor.strengths_summary || null,
                    improvement_summary: editor.improvement_summary || null,
                    career_goals: editor.career_goals || null,
                    status,
                    sections: editor.sections,
                    projects: editor.projects,
                  },
                });
              }}
              saving={updateReviewMutation.isPending}
              onDeleteRequest={setDeleteTarget}
              onImportProjects={
                selectedReview
                  ? () => importProjectsMutation.mutate(selectedReview.id)
                  : undefined
              }
              importingProjects={importProjectsMutation.isPending}
            />
          </Grid>
        </Grid>
      ) : null}

      <DeleteDialog
        open={Boolean(deleteTarget)}
        objectLabel="performance review"
        objectName={
          deleteTarget
            ? `${deleteTarget.employee_name} · ${deleteTarget.period_label}`
            : ''
        }
        extraMessage="All ratings and comments on this sheet will be removed from active review lists."
        loading={deleteReviewMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteReviewMutation.mutate(deleteTarget.id);
        }}
      />
    </Stack>
  );
}

function ReviewListCard({
  title,
  rows,
  selectedId,
  onSelect,
  emptyLabel,
  embedded = false,
}: {
  title: string;
  rows: Array<{
    id: string;
    primary: string;
    secondary: string;
    status: string;
    score?: number | string | null;
  }>;
  selectedId: string;
  onSelect: (id: string) => void;
  emptyLabel: string;
  embedded?: boolean;
}) {
  const content = (
    <>
      {!embedded ? <Typography sx={{ fontWeight: 700, mb: 1.5 }}>{title}</Typography> : null}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{embedded ? 'Employee' : 'Period'}</TableCell>
            <TableCell>Status</TableCell>
            <TableCell align="right">Score</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.id}
              hover
              selected={selectedId === row.id}
              onClick={() => onSelect(row.id)}
              sx={{ cursor: 'pointer' }}
            >
              <TableCell>
                <Typography sx={{ fontWeight: 600 }}>{row.primary}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {row.secondary}
                </Typography>
              </TableCell>
              <TableCell>
                <Chip size="small" label={row.status} color={statusChipColor(row.status)} variant="outlined" />
              </TableCell>
              <TableCell align="right">{formatScore(row.score)}</TableCell>
            </TableRow>
          ))}
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={3}>
                <Typography color="text.secondary">{emptyLabel}</Typography>
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </>
  );

  if (embedded) return content;

  return (
    <FinanceSection title={title}>
      {content}
    </FinanceSection>
  );
}

function ReviewDetailCard({
  review,
  editor,
  ratingScale,
  canManage,
  onChange,
  onSave,
  onEmployeeSave,
  onAcknowledge,
  onDeleteRequest,
  onImportProjects,
  importingProjects = false,
  saving,
}: {
  review: Review | null;
  editor: EditorState | null;
  ratingScale: RatingScaleItem[];
  canManage: boolean;
  onChange: (next: EditorState | null) => void;
  onSave?: (status: string) => void;
  onEmployeeSave?: () => void;
  onAcknowledge?: () => void;
  onDeleteRequest?: (review: Review) => void;
  onImportProjects?: () => void;
  importingProjects?: boolean;
  saving: boolean;
}) {
  const formRef = useRef<HTMLDivElement | null>(null);

  if (!review || !editor) {
    return (
      <FinanceSection title="Review form" subtitle="Select a review to inspect or edit.">
        <Typography color="text.secondary">No review selected.</Typography>
      </FinanceSection>
    );
  }

  const actions = (
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
      {canManage && onImportProjects ? (
        <Button size="small" variant="outlined" disabled={importingProjects} onClick={onImportProjects}>
          Refresh projects
        </Button>
      ) : null}
      {canManage && onDeleteRequest ? (
        <Button
          size="small"
          color="error"
          variant="outlined"
          disabled={saving}
          onClick={() => onDeleteRequest(review)}
        >
          Delete
        </Button>
      ) : null}
      {canManage && onSave ? (
        <>
          <Button size="small" variant="outlined" disabled={saving} onClick={() => onSave('draft')}>
            Save Draft
          </Button>
          <Button size="small" variant="contained" disabled={saving} onClick={() => onSave('submitted')}>
            Submit
          </Button>
        </>
      ) : null}
      {!canManage && review.status !== 'acknowledged' && onEmployeeSave ? (
        <Button size="small" variant="outlined" disabled={saving} onClick={onEmployeeSave}>
          Save My Comments
        </Button>
      ) : null}
      {!canManage && review.can_acknowledge && onAcknowledge ? (
        <Button size="small" variant="contained" disabled={saving} onClick={onAcknowledge}>
          Acknowledge
        </Button>
      ) : null}
    </Stack>
  );

  return (
    <PerformanceReviewFormDocument
      review={review}
      editor={editor}
      ratingScale={ratingScale}
      canManage={canManage}
      formRef={formRef}
      onChange={(next) => onChange(next)}
      actions={actions}
    />
  );
}

export default PerformanceReviewsPage;
