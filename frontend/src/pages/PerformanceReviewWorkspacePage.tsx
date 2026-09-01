import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Chip,
  Stack,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { apiClient, getErrorMessage } from '../api/client';
import { fetchPerformanceReview, fetchPerformanceReviewTemplate } from '../api/performanceReviews';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { DeleteDialog } from '../components/ui/design-system/DeleteDialog';
import { FullScreenFormWorkspace } from '../components/forms/FullScreenFormWorkspace';
import { PerformanceReviewFormDocument } from '../components/performanceReview/PerformanceReviewFormDocument';
import { PerformanceReviewStageStepper } from '../components/performanceReview/PerformanceReviewStageStepper';
import {
  FALLBACK_RATING_SCALE,
} from '../components/performanceReview/performanceReviewConstants';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useDirtyForm } from '../hooks/useDirtyForm';
import { useNavigationBlocker } from '../hooks/useNavigationBlocker';
import type { PerformanceReview } from '../types/PerformanceReview';
import {
  buildWorkspaceSections,
  reviewToEditor,
  scrollToWorkspaceSection,
} from '../utils/performanceReviewEditor';
import {
  countRatedItems,
  getReviewDisplayStatus,
  reviewYearFromReview,
} from '../utils/performanceReviewListing';
import {
  getPerformanceReviewFormMode,
} from '../utils/performanceReviewPermissions';

export function PerformanceReviewWorkspacePage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get('return') || '/performance/reviews';
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLDivElement | null>(null);
  const [activeSectionId, setActiveSectionId] = useState('employee-info');
  const [submitConfirmOpen, setSubmitConfirmOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PerformanceReview | null>(null);
  const [publishTarget, setPublishTarget] = useState<PerformanceReview | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);

  const reviewQuery = useQuery({
    queryKey: ['performance-reviews', reviewId],
    queryFn: () => fetchPerformanceReview(reviewId!),
    enabled: Boolean(reviewId),
  });

  const templateQuery = useQuery({
    queryKey: ['performance-reviews', 'template', reviewQuery.data?.cycle_kind || 'annual'],
    queryFn: () =>
      fetchPerformanceReviewTemplate(
        (reviewQuery.data?.cycle_kind as 'annual' | 'quarterly') || 'annual',
      ),
    enabled: Boolean(reviewQuery.data),
  });

  const baseline = useMemo(
    () => (reviewQuery.data ? reviewToEditor(reviewQuery.data) : reviewToEditor({
      id: '',
      employee_id: '',
      employee_name: '',
      reviewer_id: '',
      reviewer_name: '',
      period_label: '',
      status: 'draft',
      sections: [],
      is_editable: false,
      can_acknowledge: false,
    })),
    [reviewQuery.data],
  );

  const { form: editor, setForm: setEditor, isDirty, reset, markClean } = useDirtyForm(
    baseline,
    Boolean(reviewQuery.data),
  );

  const { blocked, confirmLeave, cancelLeave } = useNavigationBlocker(isDirty);

  useEffect(() => {
    if (reviewQuery.data) {
      markClean(reviewToEditor(reviewQuery.data));
    }
  }, [reviewQuery.data?.id, reviewQuery.data?.updated_at]);

  const updateReviewMutation = useMutation({
    mutationFn: async (payload: { id: string; body: Record<string, unknown> }) =>
      (await apiClient.patch<PerformanceReview>(`/hr/reviews/${payload.id}`, payload.body)).data,
    onSuccess: (review) => {
      showSuccess('Performance review saved');
      markClean(reviewToEditor(review));
      setLastSavedAt(new Date());
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const workflowMutation = useMutation({
    mutationFn: async (payload: {
      id: string;
      action: string;
      acknowledgement_signature?: string;
      calibration_notes?: string;
    }) =>
      (
        await apiClient.post<PerformanceReview>(`/hr/reviews/${payload.id}/workflow`, {
          action: payload.action,
          acknowledgement_signature: payload.acknowledgement_signature,
          calibration_notes: payload.calibration_notes,
        })
      ).data,
    onSuccess: (review) => {
      showSuccess('Review workflow updated');
      markClean(reviewToEditor(review));
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const deleteReviewMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/hr/reviews/${id}`);
    },
    onSuccess: () => {
      showSuccess('Performance review deleted');
      navigate(returnTo);
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const publishReviewMutation = useMutation({
    mutationFn: async (id: string) =>
      (await apiClient.post<PerformanceReview>(`/hr/reviews/${id}/publish`)).data,
    onSuccess: (review) => {
      showSuccess(`Performance review published for ${review.employee_name}`);
      setPublishTarget(null);
      markClean(reviewToEditor(review));
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const importProjectsMutation = useMutation({
    mutationFn: async (id: string) =>
      (
        await apiClient.patch<PerformanceReview>(`/hr/reviews/${id}`, {
          import_suggested_projects: true,
        })
      ).data,
    onSuccess: (review) => {
      showSuccess('Assigned projects imported from ProTrack');
      markClean(reviewToEditor(review));
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  if (!reviewId) return <ErrorState error="Review ID is missing." />;
  if (reviewQuery.isLoading) return <LoadingState message="Loading performance review…" />;
  if (reviewQuery.error) return <ErrorState error={reviewQuery.error} />;
  if (!reviewQuery.data) return <ErrorState error="Performance review not found." />;

  const review = reviewQuery.data;
  const ratingScale = templateQuery.data?.rating_scale ?? FALLBACK_RATING_SCALE;
  const formMode = getPerformanceReviewFormMode(user, review);
  const display = getReviewDisplayStatus(review);
  const isViewOnly = formMode === 'view' || !display.editable;
  const canEditEmployee = Boolean(review.can_edit_employee_section);
  const canEditManager = Boolean(review.can_edit_manager_section);
  const canManageWorkflow = Boolean(
    review.can_submit_manager ||
      review.can_calibrate ||
      review.can_publish ||
      review.can_delete,
  );
  const isEmployee = review.employee_id === user?.id;
  const reviewYear = reviewYearFromReview(review);
  const ratedCounts = countRatedItems(review);
  const progressPercent = review.completion_percent ?? 0;
  const workspaceSections = buildWorkspaceSections(review);

  const handleBack = () => {
    if (isDirty) {
      if (!window.confirm('You have unsaved changes. Leave without saving?')) return;
    }
    navigate(returnTo);
  };

  const saveDraft = () => {
    if (!review || isViewOnly) return;
    if (canEditManager) {
      updateReviewMutation.mutate({
        id: review.id,
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
          status: 'draft',
          sections: editor.sections,
          projects: editor.projects,
        },
      });
    } else {
      updateReviewMutation.mutate({
        id: review.id,
        body: {
          employee_summary: editor.employee_summary || null,
          career_goals: editor.career_goals || null,
          sections: editor.sections,
          projects: editor.projects,
        },
      });
    }
  };

  const submitReview = () => {
    if (!review || !canEditManager) return;
    updateReviewMutation.mutate({
      id: review.id,
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
        status: 'submitted',
        sections: editor.sections,
        projects: editor.projects,
      },
    });
    setSubmitConfirmOpen(false);
  };

  const runWorkflow = (
    action: string,
    extras?: { acknowledgement_signature?: string; calibration_notes?: string },
  ) => {
    workflowMutation.mutate({ id: review.id, action, ...extras });
  };

  const lastSavedLabel = lastSavedAt
    ? `Saved ${lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    : updateReviewMutation.isPending
      ? 'Saving…'
      : undefined;

  const footerActions = (
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
      {review.is_published ? <Chip size="small" color="success" label="Published" /> : null}
      {canManageWorkflow ? (
        <Button
          size="small"
          variant="outlined"
          disabled={importProjectsMutation.isPending}
          onClick={() => importProjectsMutation.mutate(review.id)}
        >
          Refresh projects
        </Button>
      ) : null}
      {canManageWorkflow && review.can_publish && !review.is_published ? (
        <Button size="small" variant="contained" onClick={() => setPublishTarget(review)}>
          Publish
        </Button>
      ) : null}
      {canManageWorkflow && review.can_delete && !review.is_published ? (
        <Button size="small" color="error" variant="outlined" onClick={() => setDeleteTarget(review)}>
          Delete
        </Button>
      ) : null}
      {!isViewOnly ? (
        <Button
          size="small"
          variant="outlined"
          disabled={updateReviewMutation.isPending || !isDirty}
          onClick={saveDraft}
        >
          Save draft
        </Button>
      ) : null}
      {canEditManager && !isViewOnly ? (
        <Button size="small" variant="contained" onClick={() => setSubmitConfirmOpen(true)}>
          Submit ratings
        </Button>
      ) : null}
      {review.can_submit_self ? (
        <Button
          size="small"
          variant="contained"
          disabled={workflowMutation.isPending}
          onClick={() => runWorkflow('submit-self')}
        >
          Submit self-review
        </Button>
      ) : null}
      {review.can_submit_manager ? (
        <Button
          size="small"
          variant="contained"
          disabled={workflowMutation.isPending}
          onClick={() => runWorkflow('submit-manager')}
        >
          Submit manager review
        </Button>
      ) : null}
      {review.can_acknowledge && isEmployee ? (
        <Button
          size="small"
          variant="contained"
          color="success"
          disabled={workflowMutation.isPending}
          onClick={() =>
            runWorkflow('acknowledge', {
              acknowledgement_signature:
                [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
                user?.email ||
                'Acknowledged',
            })
          }
        >
          Acknowledge
        </Button>
      ) : null}
    </Stack>
  );

  return (
    <>
      <FullScreenFormWorkspace
        title="Performance Review"
        subject={review.employee_name}
        year={reviewYear}
        statusLabel={display.label}
        statusColor={
          display.category === 'completed'
            ? 'success'
            : display.category === 'overdue'
              ? 'warning'
              : 'primary'
        }
        readOnly={isViewOnly}
        progressPercent={progressPercent}
        progressDetail={`${ratedCounts.rated} of ${ratedCounts.total} ratings`}
        lastSavedLabel={lastSavedLabel}
        breadcrumbs={[
          { label: 'Performance', onClick: () => navigate('/performance') },
          { label: 'Reviews', onClick: () => navigate('/performance/reviews') },
          { label: String(reviewYear) },
          { label: review.employee_name },
        ]}
        sections={workspaceSections}
        activeSectionId={activeSectionId}
        onSectionSelect={(id) => {
          setActiveSectionId(id);
          scrollToWorkspaceSection(id);
        }}
        onBack={handleBack}
        backLabel="Back to reviews"
        footerActions={footerActions}
        dirty={isDirty}
        saving={updateReviewMutation.isPending}
        onSave={!isViewOnly ? saveDraft : undefined}
        onDiscard={!isViewOnly ? reset : undefined}
        completionFooter={
          !isViewOnly && ratedCounts.total > ratedCounts.rated
            ? (
              <Typography variant="body2">
                {ratedCounts.total - ratedCounts.rated} rating(s) still need scores before the review is complete.
              </Typography>
            )
            : undefined
        }
      >
        <PerformanceReviewStageStepper
          review={review}
          busy={workflowMutation.isPending}
          onAction={runWorkflow}
        />

        <PerformanceReviewFormDocument
          review={review}
          editor={editor}
          ratingScale={ratingScale}
          canEditEmployeeSection={canEditEmployee}
          canEditManagerSection={canEditManager}
          canManage={canManageWorkflow}
          formRef={formRef}
          fullWidth
          readOnly={isViewOnly}
          onChange={setEditor}
        />
      </FullScreenFormWorkspace>

      <ConfirmDialog
        open={submitConfirmOpen}
        title="Submit performance review?"
        message="Once submitted, the review moves forward in the approval workflow. You may no longer be able to edit certain fields."
        confirmLabel="Submit review"
        loading={updateReviewMutation.isPending}
        onClose={() => setSubmitConfirmOpen(false)}
        onConfirm={submitReview}
      />

      <ConfirmDialog
        open={blocked}
        title="Unsaved changes"
        message="You have unsaved changes. Leave without saving?"
        confirmLabel="Leave"
        onClose={cancelLeave}
        onConfirm={confirmLeave}
      />

      <DeleteDialog
        open={Boolean(deleteTarget)}
        objectLabel="performance review"
        objectName={
          deleteTarget ? `${deleteTarget.employee_name} · ${deleteTarget.period_label}` : ''
        }
        loading={deleteReviewMutation.isPending}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteReviewMutation.mutate(deleteTarget.id)}
      />

      <ConfirmDialog
        open={Boolean(publishTarget)}
        title="Publish performance review?"
        recordName={
          publishTarget ? `${publishTarget.employee_name} · ${publishTarget.period_label}` : undefined
        }
        message="Publishing locks this review as the official record. After publish, it cannot be deleted."
        confirmLabel="Publish"
        loading={publishReviewMutation.isPending}
        onClose={() => setPublishTarget(null)}
        onConfirm={() => publishTarget && publishReviewMutation.mutate(publishTarget.id)}
      />
    </>
  );
}

export default PerformanceReviewWorkspacePage;
