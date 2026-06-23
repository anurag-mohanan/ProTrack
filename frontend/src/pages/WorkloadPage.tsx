import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchDesignerWorkload } from '../api/dashboard';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { formatNumber } from '../utils/format';

export function WorkloadPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'workload'],
    queryFn: fetchDesignerWorkload,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <>
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        Workload
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Designer capacity and hour allocation
      </Typography>

      {!data?.length ? (
        <EmptyState title="No workload data" description="Designers will appear here once projects are assigned." />
      ) : (
        <TableContainer component={Paper}>
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
      )}
    </>
  );
}
