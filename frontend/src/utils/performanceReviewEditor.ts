import type {
  PerformanceReview,
  PerformanceReviewEditorState,
  PerformanceReviewSection,
} from '../types/PerformanceReview';

export function cloneReviewSections(sections: PerformanceReviewSection[]): PerformanceReviewSection[] {
  return sections.map((section) => ({
    ...section,
    items: section.items.map((item) => ({ ...item })),
  }));
}

export function reviewToEditor(review: PerformanceReview): PerformanceReviewEditorState {
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
    sections: cloneReviewSections(review.sections ?? []),
    projects: (review.projects ?? []).map((row) => ({ ...row })),
  };
}

export function buildWorkspaceSections(review: PerformanceReview) {
  const sections = [
    { id: 'employee-info', label: 'Employee information', complete: true },
    ...review.sections.map((section, index) => ({
      id: `section-${index}`,
      label: section.title,
      complete: (section.rated_count ?? 0) > 0 && section.rated_count === section.total_count,
    })),
    { id: 'projects', label: 'Projects & achievements', complete: (review.projects?.length ?? 0) > 0 },
    { id: 'comments', label: 'Comments & goals', complete: Boolean(review.employee_summary || review.manager_summary) },
  ];
  return sections;
}

export function scrollToWorkspaceSection(sectionId: string) {
  const el = document.getElementById(`form-section-${sectionId}`);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
