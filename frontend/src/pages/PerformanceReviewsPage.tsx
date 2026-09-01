/**
 * Legacy entry — annual/quarterly review listing now uses the form workspace architecture.
 * @see PerformanceReviewListingPage
 * @see PerformanceReviewWorkspacePage
 */
import { PerformanceReviewListingPage } from './PerformanceReviewListingPage';

export function PerformanceReviewsPage({
  embedded = false,
  kind = null,
}: {
  embedded?: boolean;
  kind?: 'annual' | 'quarterly' | null;
}) {
  return <PerformanceReviewListingPage embedded={embedded} kind={kind} />;
}

export default PerformanceReviewsPage;
