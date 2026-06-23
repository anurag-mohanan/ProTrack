import { useState } from 'react';
import {
  Box,
  Paper,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { StatusChip } from '../components/common/StatusChip';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import {
  getCustomerSummaryReport,
  getDesignerUtilizationReport,
  getProjectHoursReport,
  reportQueryKeys,
} from '../services/reportService';
import type { ProjectStatus } from '../types';
import { formatNumber } from '../utils/format';

export function ReportsPage() {
  const [tab, setTab] = useState(0);

  const projectHoursQuery = useQuery({
    queryKey: reportQueryKeys.projectHours,
    queryFn: getProjectHoursReport,
  });

  const designerQuery = useQuery({
    queryKey: reportQueryKeys.designerUtilization,
    queryFn: getDesignerUtilizationReport,
  });

  const customerQuery = useQuery({
    queryKey: reportQueryKeys.customerSummary,
    queryFn: getCustomerSummaryReport,
  });

  const isLoading =
    projectHoursQuery.isLoading || designerQuery.isLoading || customerQuery.isLoading;

  if (isLoading) return <LoadingState message="Loading reports…" />;

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        Reports
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Portfolio hours, designer utilization, and customer summaries
      </Typography>

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 3 }}>
        <Tab label="Project Hours" />
        <Tab label="Designer Utilization" />
        <Tab label="Customer Summary" />
      </Tabs>

      {tab === 0 && (
        <>
          {projectHoursQuery.error ? (
            <ErrorState error={projectHoursQuery.error} />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Tool Number</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell>Customer</TableCell>
                    <TableCell align="right">Quoted</TableCell>
                    <TableCell align="right">Actual</TableCell>
                    <TableCell align="right">Variance</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(projectHoursQuery.data ?? []).map((row) => (
                    <TableRow key={row.project_id} hover>
                      <TableCell>{row.tool_number}</TableCell>
                      <TableCell>{row.part_description}</TableCell>
                      <TableCell>{row.customer_name}</TableCell>
                      <TableCell align="right">{formatNumber(row.quoted_hours)}</TableCell>
                      <TableCell align="right">{formatNumber(row.actual_hours)}</TableCell>
                      <TableCell align="right">{formatNumber(row.hours_variance)}</TableCell>
                      <TableCell>
                        <StatusChip status={row.status as ProjectStatus} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}

      {tab === 1 && (
        <>
          {designerQuery.error ? (
            <ErrorState error={designerQuery.error} />
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
                  {(designerQuery.data ?? []).map((row) => (
                    <TableRow key={row.user_id} hover>
                      <TableCell>{row.designer_name}</TableCell>
                      <TableCell>{row.role}</TableCell>
                      <TableCell align="right">{row.active_projects}</TableCell>
                      <TableCell align="right">{formatNumber(row.hours_this_week)}</TableCell>
                      <TableCell align="right">
                        {formatNumber(row.quoted_hours_assigned)}
                      </TableCell>
                      <TableCell align="right">
                        {formatNumber(row.actual_hours_logged)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}

      {tab === 2 && (
        <>
          {customerQuery.error ? (
            <ErrorState error={customerQuery.error} />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Customer</TableCell>
                    <TableCell align="right">Projects</TableCell>
                    <TableCell align="right">Quoted Hours</TableCell>
                    <TableCell align="right">Actual Hours</TableCell>
                    <TableCell align="right">Variance</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(customerQuery.data ?? []).map((row) => (
                    <TableRow key={row.customer_id} hover>
                      <TableCell>{row.customer_name}</TableCell>
                      <TableCell align="right">{row.project_count}</TableCell>
                      <TableCell align="right">
                        {formatNumber(row.total_quoted_hours)}
                      </TableCell>
                      <TableCell align="right">
                        {formatNumber(row.total_actual_hours)}
                      </TableCell>
                      <TableCell align="right">{formatNumber(row.hours_variance)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}
    </Box>
  );
}
