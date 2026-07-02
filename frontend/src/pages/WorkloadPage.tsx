import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchDesignerWorkload } from '../api/dashboard';
import { PageContainer } from '../components/common/PageContainer';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import { formatNumber } from '../utils/format';

export function WorkloadPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'workload'],
    queryFn: fetchDesignerWorkload,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <PageContainer>
      <PageHeader
        title="Workload"
        subtitle="Designer capacity and hour allocation"
      />

      {!data?.length ? (
        <EmptyState title="No workload data" description="Designers will appear here once projects are assigned." />
      ) : (
        <ContentCard title="Designer Workload" noPadding>
          <TableContainer>
            <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Designer</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Active Projects</TableCell>
                <TableCell align="right">Hours This Week</TableCell>
                <TableCell align="right">Quoted Assigned</TableCell>
                <TableCell align="right">Actual Logged</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((row) => (
                <TableRow key={row.user_id} hover>
                  <TableCell>{row.designer_name}</TableCell>
                  <TableCell>{row.role}</TableCell>
                  <TableCell align="right">{row.active_projects}</TableCell>
                  <TableCell align="right">{formatNumber(row.hours_this_week)}</TableCell>
                  <TableCell align="right">{formatNumber(row.quoted_hours_assigned)}</TableCell>
                  <TableCell align="right">{formatNumber(row.actual_hours_logged)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        </ContentCard>
      )}
    </PageContainer>
  );
}
