import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import {
  Button,
  Divider,
  Grid,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiClient, getErrorMessage } from '../api/client';
import {
  fetchMyPerformanceReviews,
  fetchPerformanceReviewCycles,
  fetchPerformanceReviewTeamMembers,
  fetchPerformanceReviewTemplate,
  fetchTeamPerformanceReviews,
} from '../api/performanceReviews';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { FinanceSection } from '../components/finance/FinanceCockpitPrimitives';
import {
  FormEmptyState,
  FormListingFilters,
  FormReviewCard,
  FormStatusQuickFilters,
  FormViewSwitcher,
  FormYearCollapsibleSection,
  FormYearSelector,
  FormYearSummary,
  type FormListViewMode,
} from '../components/forms/FormListingPrimitives';
import { PerformanceReviewHero } from '../components/performanceReview/PerformanceReviewPrimitives';
import {
  currentReviewYear,
  defaultPeriodLabel,
  reviewPeriodBounds,
} from '../components/performanceReview/performanceReviewPeriod';
import { FilterSelect } from '../components/ui/design-system/FilterSelect';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import type { PerformanceReview } from '../types/PerformanceReview';
import {
  availableDepartments,
  availableReviewYears,
  filterReviews,
  getReviewDisplayStatus,
  groupReviewsByYear,
  reviewActionLabel,
  reviewNeedsUserAction,
  reviewYearFromReview,
  type StatusQuickFilter,
} from '../utils/performanceReviewListing';
import { canCreatePerformanceReview } from '../utils/performanceReviewPermissions';
import { formatScore } from '../components/performanceReview/performanceReviewConstants';

export function PerformanceReviewListingPage({
  embedded = false,
  kind = 'annual' as 'annual' | 'quarterly' | null,
}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [yearFilter, setYearFilter] = useState<number | 'all'>(currentReviewYear());
  const [statusFilter, setStatusFilter] = useState<StatusQuickFilter>('all');
  const [filterTeamId, setFilterTeamId] = useState('');
  const [createTeamId, setCreateTeamId] = useState('');
  const [department, setDepartment] = useState('');
  const [search, setSearch] = useState('');
  const [needsActionOnly, setNeedsActionOnly] = useState(false);
  const [viewMode, setViewMode] = useState<FormListViewMode>('cards');

  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [selectedCycleId, setSelectedCycleId] = useState('');
  const [periodLabel, setPeriodLabel] = useState(defaultPeriodLabel());
  const [reviewYear, setReviewYear] = useState(currentReviewYear());
  const [dueDate, setDueDate] = useState('');

  const templateQuery = useQuery({
    queryKey: ['performance-reviews', 'template', kind || 'annual'],
    queryFn: () => fetchPerformanceReviewTemplate(kind || 'annual'),
  });

  const myReviewsQuery = useQuery({
    queryKey: ['performance-reviews', 'me'],
    queryFn: () => fetchMyPerformanceReviews(),
  });

  const teamMembersQuery = useQuery({
    queryKey: ['performance-reviews', 'team-members'],
    queryFn: fetchPerformanceReviewTeamMembers,
  });

  const cyclesQuery = useQuery({
    queryKey: ['performance-reviews', 'cycles'],
    queryFn: fetchPerformanceReviewCycles,
  });

  const teamReviewsQuery = useQuery({
    queryKey: ['performance-reviews', 'team', filterTeamId || 'all', kind || 'all'],
    queryFn: () =>
      fetchTeamPerformanceReviews({
        teamId: filterTeamId || undefined,
        kind: kind || undefined,
      }),
    enabled: (teamMembersQuery.data?.length ?? 0) > 0,
  });

  const createReviewMutation = useMutation({
    mutationFn: async () => {
      const member = (teamMembersQuery.data ?? []).find((row) => row.user_id === selectedMemberId);
      const teamIdForCreate = createTeamId || member?.team_id || '';
      if (!selectedMemberId || !teamIdForCreate) {
        throw new Error('Select a team member to create a review.');
      }
      return (
        await apiClient.post<PerformanceReview>('/hr/reviews', {
          employee_id: selectedMemberId,
          reviewer_id: user?.id,
          team_id: teamIdForCreate,
          cycle_id: selectedCycleId || null,
          template_id: templateQuery.data?.template_id || null,
          period_label: periodLabel || defaultPeriodLabel(reviewYear),
          review_year: reviewYear,
          due_date: dueDate || null,
        })
      ).data;
    },
    onSuccess: (review) => {
      showSuccess('Performance review created');
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
      navigate(`/performance/reviews/${review.id}`);
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const teamMembers = teamMembersQuery.data ?? [];
  const canCreateReviews = canCreatePerformanceReview(user, teamMembers.length > 0);

  const teamOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of teamMembers) {
      if (!seen.has(row.team_id)) seen.set(row.team_id, row.team_name);
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
  }, [teamMembers]);

  const filteredMembers = useMemo(
    () => teamMembers.filter((row) => !createTeamId || row.team_id === createTeamId),
    [createTeamId, teamMembers],
  );

  const filteredCycles = useMemo(() => {
    const rows = cyclesQuery.data ?? [];
    if (!kind) return rows;
    return rows.filter((row) => (row.kind || 'annual') === kind);
  }, [cyclesQuery.data, kind]);

  const allReviews = useMemo(() => {
    const map = new Map<string, PerformanceReview>();
    for (const review of myReviewsQuery.data ?? []) {
      if (!kind || (review.cycle_kind || 'annual') === kind) map.set(review.id, review);
    }
    for (const review of teamReviewsQuery.data ?? []) {
      map.set(review.id, review);
    }
    return Array.from(map.values());
  }, [myReviewsQuery.data, teamReviewsQuery.data, kind]);

  const years = availableReviewYears(allReviews);
  const departmentOptions = availableDepartments(allReviews);

  const filteredReviews = useMemo(
    () =>
      filterReviews(allReviews, {
        year: yearFilter,
        status: statusFilter,
        teamId: filterTeamId,
        department,
        search,
        needsActionOnly,
        userId: user?.id,
        kind,
      }),
    [
      allReviews,
      yearFilter,
      statusFilter,
      filterTeamId,
      department,
      search,
      needsActionOnly,
      user?.id,
      kind,
    ],
  );

  const needsActionReviews = useMemo(
    () => allReviews.filter((review) => reviewNeedsUserAction(review, user?.id)),
    [allReviews, user?.id],
  );

  const yearGroups = useMemo(() => groupReviewsByYear(filteredReviews), [filteredReviews]);

  const openReview = (reviewId: string) => {
    const returnPath = embedded ? '/performance?section=annual' : '/performance/reviews';
    navigate(`/performance/reviews/${reviewId}?return=${encodeURIComponent(returnPath)}`);
  };

  const clearFilters = () => {
    setYearFilter(currentReviewYear());
    setStatusFilter('all');
    setFilterTeamId('');
    setDepartment('');
    setSearch('');
    setNeedsActionOnly(false);
  };

  const kindLabel = kind === 'quarterly' ? 'Quarterly' : 'Annual';

  if (myReviewsQuery.isLoading || teamMembersQuery.isLoading || templateQuery.isLoading) {
    return <LoadingState message="Loading performance reviews…" />;
  }

  const renderReviewRows = (reviews: PerformanceReview[]) => {
    if (viewMode === 'list') {
      return (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Employee</TableCell>
              <TableCell>Team</TableCell>
              <TableCell>Year</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Progress</TableCell>
              <TableCell align="right">Score</TableCell>
              <TableCell align="right">Action</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {reviews.map((review) => {
              const display = getReviewDisplayStatus(review);
              return (
                <TableRow key={review.id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{review.employee_name}</TableCell>
                  <TableCell>{review.team_name ?? '—'}</TableCell>
                  <TableCell>{reviewYearFromReview(review)}</TableCell>
                  <TableCell>{display.label}</TableCell>
                  <TableCell align="right">{review.completion_percent ?? 0}%</TableCell>
                  <TableCell align="right">{formatScore(review.overall_score)}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => openReview(review.id)}>
                      {reviewActionLabel(review, user?.id)}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      );
    }

    return (
      <Grid container spacing={1.5}>
        {reviews.map((review) => (
          <Grid key={review.id} size={{ xs: 12, md: 6, lg: 4 }}>
            <FormReviewCard
              review={review}
              userId={user?.id}
              onOpen={() => openReview(review.id)}
            />
          </Grid>
        ))}
      </Grid>
    );
  };

  const renderGroupedByStatus = (reviews: PerformanceReview[]) => {
    const buckets: Record<string, PerformanceReview[]> = {
      in_progress: [],
      pending_review: [],
      overdue: [],
      not_started: [],
      completed: [],
    };
    for (const review of reviews) {
      const category = getReviewDisplayStatus(review).category;
      buckets[category].push(review);
    }

    const sections = [
      { key: 'in_progress', title: 'In progress', rows: buckets.in_progress },
      { key: 'pending_review', title: 'Pending review', rows: buckets.pending_review },
      { key: 'overdue', title: 'Overdue', rows: buckets.overdue },
      { key: 'not_started', title: 'Not started', rows: buckets.not_started },
      { key: 'completed', title: 'Completed', rows: buckets.completed },
    ];

    return (
      <Stack spacing={2.5}>
        {sections.map((section) =>
          section.rows.length === 0 ? null : (
            <BoxSection key={section.key} title={section.title} count={section.rows.length}>
              {renderReviewRows(section.rows)}
            </BoxSection>
          ),
        )}
      </Stack>
    );
  };

  return (
    <Stack spacing={2.5}>
      {!embedded ? (
        <PageHeader
          title={`${kindLabel} Performance Reviews`}
          subtitle="Year-organized review workspace with full-screen editing and workflow tracking."
        />
      ) : null}

      <PerformanceReviewHero
        formCode={templateQuery.data?.form_code ?? 'PP-HRD-FO-20'}
        formTitle={templateQuery.data?.form_title ?? 'Employee Performance Review'}
        periodLabel={defaultPeriodLabel(yearFilter === 'all' ? currentReviewYear() : yearFilter)}
      />

      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={1.5}
        sx={{ alignItems: { md: 'center' }, justifyContent: 'space-between' }}
      >
        <FormYearSelector years={years} value={yearFilter} onChange={setYearFilter} />
        <FormViewSwitcher value={viewMode} onChange={setViewMode} />
      </Stack>

      <FormStatusQuickFilters value={statusFilter} onChange={setStatusFilter} />

      <FormListingFilters
        teamOptions={teamOptions}
        departmentOptions={departmentOptions}
        teamId={filterTeamId}
        department={department}
        search={search}
        needsActionOnly={needsActionOnly}
        onTeamChange={setFilterTeamId}
        onDepartmentChange={setDepartment}
        onSearchChange={setSearch}
        onNeedsActionChange={setNeedsActionOnly}
      />

      {yearFilter !== 'all' ? (
        <FormYearSummary
          year={yearFilter}
          total={filteredReviews.length}
          completed={filteredReviews.filter((r) => getReviewDisplayStatus(r).category === 'completed').length}
          inProgress={filteredReviews.filter((r) => getReviewDisplayStatus(r).category === 'in_progress').length}
          pending={filteredReviews.filter((r) => getReviewDisplayStatus(r).category === 'pending_review').length}
          overdue={filteredReviews.filter((r) => getReviewDisplayStatus(r).category === 'overdue').length}
        />
      ) : null}

      {needsActionReviews.length > 0 && !needsActionOnly ? (
        <FinanceSection title="Needs my action" subtitle={`${needsActionReviews.length} review(s) awaiting your input`}>
          {renderReviewRows(needsActionReviews.slice(0, 6))}
        </FinanceSection>
      ) : null}

      {filteredReviews.length === 0 ? (
        <FormEmptyState
          title={`No ${kindLabel.toLowerCase()} reviews for selected filters`}
          message="There are no performance reviews matching your current year, status, or search filters."
          onClear={clearFilters}
        />
      ) : yearFilter === 'all' ? (
        yearGroups.map((group) => (
          <FormYearCollapsibleSection
            key={group.year}
            year={group.year}
            count={group.reviews.length}
            defaultExpanded={group.year === currentReviewYear()}
          >
            <FormYearSummary
              year={group.year}
              total={group.reviews.length}
              completed={group.completed}
              inProgress={group.inProgress}
              pending={group.pending}
              overdue={group.overdue}
            />
            {renderGroupedByStatus(group.reviews)}
          </FormYearCollapsibleSection>
        ))
      ) : (
        renderGroupedByStatus(filteredReviews)
      )}

      {canCreateReviews ? (
        <FinanceSection
          title="Create review"
          subtitle="Launch a new sheet from the active template"
        >
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, md: 3 }}>
              <FilterSelect label="Team" value={createTeamId} onChange={(e) => setCreateTeamId(String(e.target.value))}>
                <MenuItem value="">All teams</MenuItem>
                {teamOptions.map((team) => (
                  <MenuItem key={team.id} value={team.id}>{team.name}</MenuItem>
                ))}
              </FilterSelect>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FilterSelect
                label="Team member"
                value={selectedMemberId}
                onChange={(e) => setSelectedMemberId(String(e.target.value))}
              >
                <MenuItem value=""><em>Select member</em></MenuItem>
                {filteredMembers.map((member) => (
                  <MenuItem key={`${member.team_id}-${member.user_id}`} value={member.user_id}>
                    {createTeamId ? member.name : `${member.name} · ${member.team_name}`}
                  </MenuItem>
                ))}
              </FilterSelect>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FilterSelect
                label="Cycle"
                value={selectedCycleId}
                onChange={(e) => setSelectedCycleId(String(e.target.value))}
              >
                <MenuItem value="">No cycle</MenuItem>
                {filteredCycles.map((cycle) => (
                  <MenuItem key={cycle.id} value={cycle.id}>{cycle.title}</MenuItem>
                ))}
              </FilterSelect>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label="Review year"
                value={reviewYear}
                onChange={(e) => {
                  const nextYear = Number(e.target.value) || currentReviewYear();
                  setReviewYear(nextYear);
                  setPeriodLabel(defaultPeriodLabel(nextYear));
                }}
                helperText={`${reviewPeriodBounds(reviewYear).start} → ${reviewPeriodBounds(reviewYear).end}`}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                size="small"
                label="Period label"
                value={periodLabel}
                onChange={(e) => setPeriodLabel(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="Due date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Button
                fullWidth
                variant="contained"
                sx={{ height: 40 }}
                disabled={!selectedMemberId || createReviewMutation.isPending}
                onClick={() => createReviewMutation.mutate()}
              >
                Create review sheet
              </Button>
            </Grid>
          </Grid>
        </FinanceSection>
      ) : null}
    </Stack>
  );
}

function BoxSection({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <Stack spacing={1.25}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>{title}</Typography>
        <Typography variant="caption" color="text.secondary">{count}</Typography>
      </Stack>
      <Divider />
      {children}
    </Stack>
  );
}

export default PerformanceReviewListingPage;
