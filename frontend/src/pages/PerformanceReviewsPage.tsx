import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, getErrorMessage } from '../api/client';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

type ReviewItem = {
  id?: string;
  prompt: string;
  rating?: number | string | null;
  employee_comment?: string | null;
  manager_comment?: string | null;
  sort_order: number;
};

type ReviewSection = {
  id?: string;
  title: string;
  description?: string | null;
  sort_order: number;
  items: ReviewItem[];
};

type Review = {
  id: string;
  employee_id: string;
  employee_name: string;
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
  overall_score?: number | string | null;
  employee_summary?: string | null;
  manager_summary?: string | null;
  strengths_summary?: string | null;
  improvement_summary?: string | null;
  career_goals?: string | null;
  submitted_at?: string | null;
  acknowledged_at?: string | null;
  sections: ReviewSection[];
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

type EditorState = {
  period_label: string;
  review_date: string;
  due_date: string;
  overall_score: string;
  employee_summary: string;
  manager_summary: string;
  strengths_summary: string;
  improvement_summary: string;
  career_goals: string;
  sections: ReviewSection[];
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
  };
}

export function PerformanceReviewsPage() {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [selectedReviewId, setSelectedReviewId] = useState<string>('');
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [selectedCycleId, setSelectedCycleId] = useState('');
  const [periodLabel, setPeriodLabel] = useState(new Date().getFullYear().toString());
  const [dueDate, setDueDate] = useState('');
  const [editor, setEditor] = useState<EditorState | null>(null);

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
    mutationFn: async () =>
      (
        await apiClient.post<Review>('/hr/reviews', {
          employee_id: selectedMemberId,
          reviewer_id: user?.id,
          team_id: selectedTeamId,
          cycle_id: selectedCycleId || null,
          period_label: periodLabel,
          due_date: dueDate || null,
        })
      ).data,
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
    if (!selectedTeamId && teamOptions.length) {
      setSelectedTeamId(teamOptions[0].id);
    }
  }, [selectedTeamId, teamOptions]);

  const filteredMembers = useMemo(
    () => teamMembers.filter((row) => !selectedTeamId || row.team_id === selectedTeamId),
    [selectedTeamId, teamMembers],
  );

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

  if (myReviewsQuery.isLoading || teamMembersQuery.isLoading) {
    return <LoadingState message="Loading performance reviews…" />;
  }

  const canManageTeamReviews = teamMembers.length > 0;

  return (
    <Stack spacing={2.5}>
      <PageHeader
        title="Performance Reviews"
        subtitle="Track historical reviews, prepare new review sheets, and keep annual feedback in one structured workspace."
      />

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">My Reviews</Typography>
              <Typography variant="h5">{myReviewsQuery.data?.length ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Team Members</Typography>
              <Typography variant="h5">{teamMembers.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="caption">Review Cycles</Typography>
              <Typography variant="h5">{cyclesQuery.data?.length ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Tabs value={tab} onChange={(_, value) => setTab(value)}>
        <Tab label="My Reviews" />
        {canManageTeamReviews ? <Tab label="Team Reviews" /> : null}
      </Tabs>

      {tab === 0 ? (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card variant="outlined">
              <CardContent>
                <Typography sx={{ fontWeight: 700, mb: 1.5 }}>My review history</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Period</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(myReviewsQuery.data ?? []).map((review) => (
                      <TableRow
                        key={review.id}
                        hover
                        selected={selectedReviewId === review.id}
                        onClick={() => setSelectedReviewId(review.id)}
                        sx={{ cursor: 'pointer' }}
                      >
                        <TableCell>
                          <Typography sx={{ fontWeight: 600 }}>{review.period_label}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {review.team_name ?? 'Team'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip size="small" label={review.status} variant="outlined" />
                        </TableCell>
                      </TableRow>
                    ))}
                    {(myReviewsQuery.data ?? []).length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={2}>
                          <Typography color="text.secondary">
                            No reviews available yet.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <ReviewDetailCard
              review={selectedReview}
              editor={editor}
              canManage={false}
              onChange={setEditor}
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
            <Card variant="outlined">
              <CardContent>
                <Typography sx={{ fontWeight: 700, mb: 1.5 }}>Create team review</Typography>
                <Stack spacing={1.5}>
                  <FormControl size="small">
                    <InputLabel>Team</InputLabel>
                    <Select
                      label="Team"
                      value={selectedTeamId}
                      onChange={(e) => setSelectedTeamId(String(e.target.value))}
                    >
                      {teamOptions.map((team) => (
                        <MenuItem key={team.id} value={team.id}>
                          {team.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small">
                    <InputLabel>Team member</InputLabel>
                    <Select
                      label="Team member"
                      value={selectedMemberId}
                      onChange={(e) => setSelectedMemberId(String(e.target.value))}
                    >
                      {filteredMembers.map((member) => (
                        <MenuItem key={member.user_id} value={member.user_id}>
                          {member.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small">
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
                    disabled={!selectedTeamId || !selectedMemberId || createReviewMutation.isPending}
                    onClick={() => createReviewMutation.mutate()}
                  >
                    Create Review Sheet
                  </Button>
                </Stack>
                <Divider sx={{ my: 2 }} />
                <Typography sx={{ fontWeight: 700, mb: 1 }}>Existing team reviews</Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Employee</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(teamReviewsQuery.data ?? []).map((review) => (
                      <TableRow
                        key={review.id}
                        hover
                        selected={selectedReviewId === review.id}
                        onClick={() => setSelectedReviewId(review.id)}
                        sx={{ cursor: 'pointer' }}
                      >
                        <TableCell>
                          <Typography sx={{ fontWeight: 600 }}>{review.employee_name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {review.period_label}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip size="small" label={review.status} variant="outlined" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <ReviewDetailCard
              review={selectedReview}
              editor={editor}
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
                    overall_score: editor.overall_score ? Number(editor.overall_score) : null,
                    employee_summary: editor.employee_summary || null,
                    manager_summary: editor.manager_summary || null,
                    strengths_summary: editor.strengths_summary || null,
                    improvement_summary: editor.improvement_summary || null,
                    career_goals: editor.career_goals || null,
                    status,
                    sections: editor.sections,
                  },
                });
              }}
              saving={updateReviewMutation.isPending}
            />
          </Grid>
        </Grid>
      ) : null}
    </Stack>
  );
}

function ReviewDetailCard({
  review,
  editor,
  canManage,
  onChange,
  onSave,
  onAcknowledge,
  saving,
}: {
  review: Review | null;
  editor: EditorState | null;
  canManage: boolean;
  onChange: (next: EditorState | null) => void;
  onSave?: (status: string) => void;
  onAcknowledge?: () => void;
  saving: boolean;
}) {
  if (!review || !editor) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography color="text.secondary">
            Select a review to inspect or edit.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const setField = (field: keyof EditorState, value: string) =>
    onChange({ ...editor, [field]: value });

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 2, gap: 1 }}>
          <Box>
            <Typography sx={{ fontWeight: 800 }}>{review.employee_name}</Typography>
            <Typography variant="body2" color="text.secondary">
              {review.team_name ?? 'Team'} · Reviewer {review.reviewer_name}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Chip size="small" label={review.status} />
            {review.cycle_title ? <Chip size="small" variant="outlined" label={review.cycle_title} /> : null}
          </Stack>
        </Stack>

        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth
              size="small"
              label="Period"
              value={editor.period_label}
              onChange={(e) => setField('period_label', e.target.value)}
              disabled={!canManage}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label="Review date"
              value={editor.review_date}
              onChange={(e) => setField('review_date', e.target.value)}
              disabled={!canManage}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label="Due date"
              value={editor.due_date}
              onChange={(e) => setField('due_date', e.target.value)}
              disabled={!canManage}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Grid>
        </Grid>

        <Stack spacing={1.5}>
          <TextField
            fullWidth
            size="small"
            label="Overall score (0-5)"
            value={editor.overall_score}
            onChange={(e) => setField('overall_score', e.target.value)}
            disabled={!canManage}
          />
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            label="Employee summary"
            value={editor.employee_summary}
            onChange={(e) => setField('employee_summary', e.target.value)}
            disabled={canManage ? false : false}
          />
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            label="Manager summary"
            value={editor.manager_summary}
            onChange={(e) => setField('manager_summary', e.target.value)}
            disabled={!canManage}
          />
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            label="Strengths"
            value={editor.strengths_summary}
            onChange={(e) => setField('strengths_summary', e.target.value)}
            disabled={!canManage}
          />
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            label="Improvement areas"
            value={editor.improvement_summary}
            onChange={(e) => setField('improvement_summary', e.target.value)}
            disabled={!canManage}
          />
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            label="Career goals"
            value={editor.career_goals}
            onChange={(e) => setField('career_goals', e.target.value)}
          />
        </Stack>

        <Divider sx={{ my: 2 }} />

        <Stack spacing={2}>
          {editor.sections.map((section, sectionIndex) => (
            <Box key={section.id ?? `${section.title}-${sectionIndex}`}>
              <Typography sx={{ fontWeight: 700 }}>{section.title}</Typography>
              {section.description ? (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {section.description}
                </Typography>
              ) : null}
              <Stack spacing={1}>
                {section.items.map((item, itemIndex) => (
                  <Card key={item.id ?? `${item.prompt}-${itemIndex}`} variant="outlined">
                    <CardContent>
                      <Typography sx={{ fontWeight: 600, mb: 1 }}>{item.prompt}</Typography>
                      <Grid container spacing={1.5}>
                        <Grid size={{ xs: 12, sm: 3 }}>
                          <TextField
                            fullWidth
                            size="small"
                            label="Rating"
                            value={item.rating ?? ''}
                            onChange={(e) => {
                              const sections = cloneSections(editor.sections);
                              sections[sectionIndex].items[itemIndex].rating = e.target.value;
                              onChange({ ...editor, sections });
                            }}
                            disabled={!canManage}
                          />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 9 }}>
                          <TextField
                            fullWidth
                            size="small"
                            multiline
                            minRows={2}
                            label="Manager comment"
                            value={item.manager_comment ?? ''}
                            onChange={(e) => {
                              const sections = cloneSections(editor.sections);
                              sections[sectionIndex].items[itemIndex].manager_comment =
                                e.target.value;
                              onChange({ ...editor, sections });
                            }}
                            disabled={!canManage}
                          />
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <TextField
                            fullWidth
                            size="small"
                            multiline
                            minRows={2}
                            label="Employee comment"
                            value={item.employee_comment ?? ''}
                            onChange={(e) => {
                              const sections = cloneSections(editor.sections);
                              sections[sectionIndex].items[itemIndex].employee_comment =
                                e.target.value;
                              onChange({ ...editor, sections });
                            }}
                          />
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>

        <Stack direction="row" spacing={1} sx={{ mt: 2, justifyContent: 'flex-end' }}>
          {canManage && onSave ? (
            <>
              <Button
                variant="outlined"
                disabled={saving}
                onClick={() => onSave('draft')}
              >
                Save Draft
              </Button>
              <Button
                variant="contained"
                disabled={saving}
                onClick={() => onSave('submitted')}
              >
                Submit Review
              </Button>
            </>
          ) : null}
          {!canManage && review.can_acknowledge && onAcknowledge ? (
            <Button variant="contained" disabled={saving} onClick={onAcknowledge}>
              Acknowledge Review
            </Button>
          ) : null}
        </Stack>
      </CardContent>
    </Card>
  );
}

export default PerformanceReviewsPage;
