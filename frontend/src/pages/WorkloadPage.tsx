import { TableRow } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchDesignerWorkload } from '../api/dashboard';
import { PageContainer } from '../components/common/PageContainer';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import {
  ClickableTableRow,
  EntityAvatar,
  OperationalDataTable,
  StickyHeaderCell,
  StickyTableCell,
  UtilizationBar,
} from '../components/ui/design-system';
import { formatDisplayValue, formatNumber } from '../utils/format';

export function WorkloadPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'workload'],
    queryFn: fetchDesignerWorkload,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <PageContainer>
      <PageHeader title="Workload" subtitle="Designer capacity and hour allocation" />

      {!data?.length ? (
        <EmptyState
          title="No workload data"
          description="Designers will appear here once projects are assigned."
        />
      ) : (
        <ContentCard title="Designer Workload" noPadding>
          <OperationalDataTable
            maxHeight={640}
            head={
              <TableRow>
                <StickyHeaderCell pinned>Designer</StickyHeaderCell>
                <StickyHeaderCell>Role</StickyHeaderCell>
                <StickyHeaderCell align="right">Active Projects</StickyHeaderCell>
                <StickyHeaderCell align="right">Hours This Week</StickyHeaderCell>
                <StickyHeaderCell>Utilization</StickyHeaderCell>
                <StickyHeaderCell align="right">Quoted Assigned</StickyHeaderCell>
                <StickyHeaderCell align="right">Actual Logged</StickyHeaderCell>
              </TableRow>
            }
          >
            {data.map((row) => {
              const utilization =
                row.quoted_hours_assigned > 0
                  ? Math.round((row.actual_hours_logged / row.quoted_hours_assigned) * 100)
                  : 0;
              return (
                <ClickableTableRow key={row.user_id}>
                  <StickyTableCell pinned>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                      <EntityAvatar label={row.designer_name} size={28} />
                      {formatDisplayValue(row.designer_name)}
                    </span>
                  </StickyTableCell>
                  <StickyTableCell>{formatDisplayValue(row.role)}</StickyTableCell>
                  <StickyTableCell align="right">{row.active_projects}</StickyTableCell>
                  <StickyTableCell align="right">{formatNumber(row.hours_this_week)}</StickyTableCell>
                  <StickyTableCell>
                    <UtilizationBar label="" value={utilization} showValue />
                  </StickyTableCell>
                  <StickyTableCell align="right">{formatNumber(row.quoted_hours_assigned)}</StickyTableCell>
                  <StickyTableCell align="right">{formatNumber(row.actual_hours_logged)}</StickyTableCell>
                </ClickableTableRow>
              );
            })}
          </OperationalDataTable>
        </ContentCard>
      )}
    </PageContainer>
  );
}
