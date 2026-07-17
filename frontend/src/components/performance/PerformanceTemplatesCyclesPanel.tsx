import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  MenuItem,
  Select,
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
import { apiClient, getErrorMessage } from '../../api/client';
import { LoadingState } from '../common/LoadingState';
import { useToast } from '../../context/ToastContext';
import { currentReviewYear } from '../performanceReview/performanceReviewPeriod';

type TemplateRow = {
  id: string;
  code: string;
  name: string;
  version: number;
  kind: string;
  is_active: boolean;
};

type CycleRow = {
  id: string;
  title: string;
  review_year: number;
  kind: string;
  template_id?: string | null;
  calibration_required: boolean;
  status: string;
  due_date?: string | null;
};

type Props = {
  canManage: boolean;
};

export function PerformanceTemplatesCyclesPanel({ canManage }: Props) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(`FY${currentReviewYear()} Annual Review`);
  const [kind, setKind] = useState<'annual' | 'quarterly'>('annual');
  const [templateId, setTemplateId] = useState('');
  const [calibrationRequired, setCalibrationRequired] = useState(false);
  const [dueDate, setDueDate] = useState('');

  const templatesQuery = useQuery({
    queryKey: ['performance', 'templates'],
    queryFn: async () =>
      (await apiClient.get<TemplateRow[]>('/hr/performance/templates')).data,
  });

  const cyclesQuery = useQuery({
    queryKey: ['performance-reviews', 'cycles'],
    queryFn: async () => (await apiClient.get<CycleRow[]>('/hr/review-cycles')).data,
  });

  const templates = templatesQuery.data ?? [];
  const kindTemplates = useMemo(
    () => templates.filter((row) => row.kind === kind),
    [templates, kind],
  );

  const createCycleMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<CycleRow>('/hr/review-cycles', {
          title,
          review_year: currentReviewYear(),
          kind,
          template_id: templateId || null,
          calibration_required: calibrationRequired,
          due_date: dueDate || null,
          status: 'draft',
        })
      ).data,
    onSuccess: () => {
      showSuccess('Review cycle created');
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews', 'cycles'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const cycleActionMutation = useMutation({
    mutationFn: async (payload: { id: string; action: 'open' | 'start-calibration' | 'close' }) =>
      (await apiClient.post<CycleRow>(`/hr/review-cycles/${payload.id}/${payload.action}`)).data,
    onSuccess: (_, vars) => {
      showSuccess(`Cycle ${vars.action.replace('-', ' ')}`);
      void queryClient.invalidateQueries({ queryKey: ['performance-reviews', 'cycles'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  if (templatesQuery.isLoading || cyclesQuery.isLoading) {
    return <LoadingState message="Loading templates & cycles…" />;
  }

  return (
    <Stack spacing={2.5}>
      <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
          Review templates
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Code</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Kind</TableCell>
              <TableCell>Version</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {templates.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.code}</TableCell>
                <TableCell>{row.name}</TableCell>
                <TableCell>{row.kind}</TableCell>
                <TableCell>v{row.version}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>

      {canManage ? (
        <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1.5 }}>
            Open a review cycle
          </Typography>
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                size="small"
                label="Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 2 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Kind</InputLabel>
                <Select
                  label="Kind"
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value as 'annual' | 'quarterly');
                    setTemplateId('');
                  }}
                >
                  <MenuItem value="annual">Annual</MenuItem>
                  <MenuItem value="quarterly">Quarterly</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Template</InputLabel>
                <Select
                  label="Template"
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                >
                  <MenuItem value="">Default for kind</MenuItem>
                  {kindTemplates.map((row) => (
                    <MenuItem key={row.id} value={row.id}>
                      {row.name} (v{row.version})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid size={{ xs: 12, md: 2 }}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="Due date"
                slotProps={{ inputLabel: { shrink: true } }}
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={calibrationRequired}
                    onChange={(e) => setCalibrationRequired(e.target.checked)}
                  />
                }
                label="Calibration required"
              />
            </Grid>
            <Grid size={{ xs: 12, md: 2 }}>
              <Button
                fullWidth
                variant="contained"
                disabled={!title.trim() || createCycleMutation.isPending}
                onClick={() => createCycleMutation.mutate()}
              >
                Create cycle
              </Button>
            </Grid>
          </Grid>
        </Box>
      ) : null}

      <Box sx={{ bgcolor: 'background.paper', borderRadius: 2, p: 2, border: 1, borderColor: 'divider' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
          Cycles
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Title</TableCell>
              <TableCell>Kind</TableCell>
              <TableCell>Year</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Calibration</TableCell>
              {canManage ? <TableCell align="right">Actions</TableCell> : null}
            </TableRow>
          </TableHead>
          <TableBody>
            {(cyclesQuery.data ?? []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.title}</TableCell>
                <TableCell>{row.kind}</TableCell>
                <TableCell>{row.review_year}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell>{row.calibration_required ? 'Yes' : 'No'}</TableCell>
                {canManage ? (
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'flex-end' }}>
                      {row.status === 'draft' ? (
                        <Button
                          size="small"
                          onClick={() => cycleActionMutation.mutate({ id: row.id, action: 'open' })}
                        >
                          Open
                        </Button>
                      ) : null}
                      {row.calibration_required && row.status === 'open' ? (
                        <Button
                          size="small"
                          onClick={() =>
                            cycleActionMutation.mutate({ id: row.id, action: 'start-calibration' })
                          }
                        >
                          Calibrate
                        </Button>
                      ) : null}
                      {row.status !== 'closed' ? (
                        <Button
                          size="small"
                          color="inherit"
                          onClick={() => cycleActionMutation.mutate({ id: row.id, action: 'close' })}
                        >
                          Close
                        </Button>
                      ) : null}
                    </Stack>
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Stack>
  );
}
