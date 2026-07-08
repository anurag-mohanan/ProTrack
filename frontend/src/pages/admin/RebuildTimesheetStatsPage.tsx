import { useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';
import {
  recalculateTimesheets,
  type TimesheetRecalculationReport,
} from '../../api/adminTimesheets';
import { invalidateTimesheetRelatedQueries } from '../../utils/queryInvalidation';

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
          {label}
        </Typography>
        <Typography sx={{ fontWeight: 800, fontSize: '1.6rem', lineHeight: 1.2 }}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

export default function RebuildTimesheetStatsPage() {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [report, setReport] = useState<TimesheetRecalculationReport | null>(null);

  const mutation = useMutation({
    mutationFn: recalculateTimesheets,
    onSuccess: (data) => {
      setReport(data);
      invalidateTimesheetRelatedQueries(queryClient);
      showSuccess('Timesheet statistics recalculated.');
    },
    onError: (error) => {
      showError(error instanceof Error ? error.message : 'Recalculation failed.');
    },
  });

  return (
    <Box>
      <PageHeader
        title="Rebuild Timesheet Statistics"
        subtitle="Recalculate all timesheet summaries and repair inconsistent data. Recommended after every historical import."
      />

      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', sm: 'row' },
              gap: 2,
              alignItems: { sm: 'center' },
              justifyContent: 'space-between',
            }}
          >
            <Box>
              <Typography sx={{ fontWeight: 700 }}>Recalculate All Timesheet Summaries</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                Rebuilds monthly, weekly, daily, leave and billable totals; recomputes remaining
                hours and project actual hours; validates orphan entries and project/task
                references; and repairs inconsistent data.
              </Typography>
            </Box>
            <ProsohmButton
              buttonVariant="primary"
              startIcon={<RefreshRoundedIcon />}
              loading={mutation.isPending}
              onClick={() => mutation.mutate()}
              sx={{ flexShrink: 0 }}
            >
              Recalculate
            </ProsohmButton>
          </Box>
        </CardContent>
      </Card>

      {report ? (
        <Card variant="outlined">
          <CardContent>
            <Typography sx={{ fontWeight: 700, mb: 2 }}>Recalculation Report</Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Users Checked" value={report.users_checked} />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Months Recalculated" value={report.months_recalculated} />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Entries Scanned" value={report.entries_scanned} />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Projects Recalculated" value={report.projects_recalculated} />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Errors Fixed" value={report.errors_fixed} />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Warnings" value={report.warnings.length} />
              </Grid>
              <Grid size={{ xs: 6, md: 3 }}>
                <StatCard label="Execution" value={`${report.execution_ms} ms`} />
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />

            {report.warnings.length ? (
              <>
                <Typography sx={{ fontWeight: 700, mb: 1 }}>Warnings</Typography>
                <List dense>
                  {report.warnings.map((warning, index) => (
                    <ListItem key={index} disableGutters>
                      <ListItemText primary={warning} />
                    </ListItem>
                  ))}
                </List>
              </>
            ) : (
              <Alert severity="success">
                No inconsistencies found. All timesheet statistics are consistent.
              </Alert>
            )}
          </CardContent>
        </Card>
      ) : null}
    </Box>
  );
}
