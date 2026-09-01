import { apiClient } from './client';
import type {
  PerformanceReview,
  PerformanceReviewCycle,
  PerformanceReviewTeamMember,
  PerformanceReviewTemplate,
} from '../types/PerformanceReview';

export async function fetchPerformanceReviewTemplate(
  kind: 'annual' | 'quarterly' = 'annual',
): Promise<PerformanceReviewTemplate> {
  const { data } = await apiClient.get<PerformanceReviewTemplate>(
    `/hr/reviews/template?kind=${kind}`,
  );
  return data;
}

export async function fetchMyPerformanceReviews(
  reviewYear?: number,
): Promise<PerformanceReview[]> {
  const params = reviewYear ? `?review_year=${reviewYear}` : '';
  const { data } = await apiClient.get<PerformanceReview[]>(`/hr/reviews/me${params}`);
  return data;
}

export async function fetchTeamPerformanceReviews(options?: {
  teamId?: string;
  kind?: 'annual' | 'quarterly';
  reviewYear?: number;
}): Promise<PerformanceReview[]> {
  const params = new URLSearchParams();
  if (options?.teamId) params.set('team_id', options.teamId);
  if (options?.kind) params.set('kind', options.kind);
  if (options?.reviewYear) params.set('review_year', String(options.reviewYear));
  const query = params.toString() ? `?${params.toString()}` : '';
  const { data } = await apiClient.get<PerformanceReview[]>(`/hr/reviews/team${query}`);
  return data;
}

export async function fetchPerformanceReviewTeamMembers(): Promise<PerformanceReviewTeamMember[]> {
  const { data } = await apiClient.get<PerformanceReviewTeamMember[]>('/hr/reviews/team-members');
  return data;
}

export async function fetchPerformanceReviewCycles(): Promise<PerformanceReviewCycle[]> {
  const { data } = await apiClient.get<PerformanceReviewCycle[]>('/hr/review-cycles');
  return data;
}

export async function fetchPerformanceReview(reviewId: string): Promise<PerformanceReview> {
  const { data } = await apiClient.get<PerformanceReview>(`/hr/reviews/${reviewId}`);
  return data;
}
