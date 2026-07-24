import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import SchoolRoundedIcon from '@mui/icons-material/SchoolRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, getErrorMessage } from '../api/client';
import { fetchUsers } from '../api/lookups';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { FilterSelect } from '../components/ui/design-system/FilterSelect';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import { userDisplayName } from '../utils/format';

type TrainingCourse = {
  id: string;
  code: string;
  title: string;
  description?: string | null;
  owner_department?: string | null;
  estimated_minutes: number;
  external_url?: string | null;
  is_required_for_onboarding: boolean;
  is_active: boolean;
};

type TrainingAssignment = {
  id: string;
  course_id: string;
  user_id: string;
  status: string;
  due_date?: string | null;
  course_title?: string | null;
  course_code?: string | null;
  estimated_minutes?: number | null;
  external_url?: string | null;
  is_required_for_onboarding?: boolean;
};

export default function TrainingPage() {
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [newTitle, setNewTitle] = useState('');
  const [newCode, setNewCode] = useState('');
  const [assignCourseId, setAssignCourseId] = useState('');
  const [assignUserId, setAssignUserId] = useState('');
  const [assignDue, setAssignDue] = useState('');

  const coursesQuery = useQuery({
    queryKey: ['hr', 'training', 'courses'],
    queryFn: async () =>
      (await apiClient.get<TrainingCourse[]>('/hr/training/courses')).data,
  });

  const mineQuery = useQuery({
    queryKey: ['hr', 'training', 'mine'],
    queryFn: async () =>
      (await apiClient.get<TrainingAssignment[]>('/hr/training/my-assignments')).data,
  });

  const allQuery = useQuery({
    queryKey: ['hr', 'training', 'assignments'],
    queryFn: async () =>
      (await apiClient.get<TrainingAssignment[]>('/hr/training/assignments')).data,
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<TrainingCourse>('/hr/training/courses', {
          code: newCode || newTitle.slice(0, 12).toUpperCase().replace(/\s+/g, '_'),
          title: newTitle,
          estimated_minutes: 30,
          is_required_for_onboarding: false,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Course created');
      setNewTitle('');
      setNewCode('');
      void queryClient.invalidateQueries({ queryKey: ['hr', 'training'] });
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const assignMutation = useMutation({
    mutationFn: async () =>
      (
        await apiClient.post<TrainingAssignment[]>('/hr/training/assign', {
          course_id: assignCourseId,
          user_ids: [assignUserId],
          due_date: assignDue || null,
        })
      ).data,
    onSuccess: () => {
      showSuccess('Training assigned — employee notified');
      setAssignUserId('');
      void queryClient.invalidateQueries({ queryKey: ['hr', 'training'] });
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const completeMutation = useMutation({
    mutationFn: async (assignmentId: string) =>
      (
        await apiClient.post<TrainingAssignment>(
          `/hr/training/assignments/${assignmentId}/complete`,
        )
      ).data,
    onSuccess: () => {
      showSuccess('Training marked complete');
      void queryClient.invalidateQueries({ queryKey: ['hr', 'training'] });
    },
    onError: (err) => showError(getErrorMessage(err)),
  });

  const mine = mineQuery.data ?? [];
  const openMine = useMemo(
    () => mine.filter((row) => row.status !== 'completed'),
    [mine],
  );
  const courses = coursesQuery.data ?? [];

  if (coursesQuery.isLoading || mineQuery.isLoading) {
    return <LoadingState message="Loading training…" />;
  }
  if (coursesQuery.error) return <ErrorState error={coursesQuery.error} />;

  return (
    <PageContainer>
      <PageHeader
        title="Employee training"
        subtitle="Common onboarding courses plus ad-hoc assignments. Required courses must be completed before onboarding can finish."
      />

      <Stack spacing={3}>
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
            My training
          </Typography>
          {openMine.length === 0 ? (
            <Typography color="text.secondary">
              {user ? 'No open training assignments.' : 'Sign in to see your courses.'}
            </Typography>
          ) : (
            <Stack spacing={1}>
              {openMine.map((row) => (
                <Stack
                  key={row.id}
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={1}
                  sx={{
                    alignItems: { sm: 'center' },
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    p: 1.25,
                  }}
                >
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ fontWeight: 700 }}>
                      {row.course_title || 'Course'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {row.estimated_minutes ?? 30} min
                      {row.due_date ? ` · due ${row.due_date}` : ''}
                      {row.is_required_for_onboarding ? ' · required for onboarding' : ''}
                    </Typography>
                  </Box>
                  {row.is_required_for_onboarding ? (
                    <Chip size="small" color="warning" label="Required" />
                  ) : null}
                  <Button
                    size="small"
                    variant="contained"
                    disabled={completeMutation.isPending}
                    onClick={() => completeMutation.mutate(row.id)}
                  >
                    Mark complete
                  </Button>
                </Stack>
              ))}
            </Stack>
          )}
        </Box>

        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
            Course catalog
          </Typography>
          <Stack spacing={0.75} sx={{ mb: 2 }}>
            {courses.map((course) => (
              <Stack key={course.id} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <SchoolRoundedIcon fontSize="small" color="action" />
                <Typography sx={{ flex: 1, fontWeight: 600 }}>
                  {course.title}
                  <Typography component="span" variant="caption" color="text.secondary">
                    {' '}
                    · {course.estimated_minutes} min · {course.owner_department || 'General'}
                  </Typography>
                </Typography>
                {course.is_required_for_onboarding ? (
                  <Chip size="small" label="Onboarding" color="primary" variant="outlined" />
                ) : (
                  <Chip size="small" label="Ad-hoc" variant="outlined" />
                )}
              </Stack>
            ))}
          </Stack>

          <Typography variant="body2" sx={{ fontWeight: 700, mb: 1 }}>
            Add course (HR)
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 2 }}>
            <TextField
              size="small"
              label="Code"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              sx={{ minWidth: 140 }}
            />
            <TextField
              size="small"
              label="Title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              sx={{ flex: 1 }}
            />
            <Button
              variant="outlined"
              disabled={!newTitle.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              Create
            </Button>
          </Stack>

          <Typography variant="body2" sx={{ fontWeight: 700, mb: 1 }}>
            Assign course (notify when available)
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <FilterSelect
              label="Course"
              value={assignCourseId}
              fullWidth={false}
              sx={{ minWidth: 220 }}
              onChange={(e) => setAssignCourseId(String(e.target.value))}
            >
              <MenuItem value="">Select course</MenuItem>
              {courses.map((course) => (
                <MenuItem key={course.id} value={course.id}>
                  {course.title}
                </MenuItem>
              ))}
            </FilterSelect>
            <FilterSelect
              label="Employee"
              value={assignUserId}
              fullWidth={false}
              sx={{ minWidth: 200 }}
              onChange={(e) => setAssignUserId(String(e.target.value))}
            >
              <MenuItem value="">Select person</MenuItem>
              {(usersQuery.data ?? []).map((u) => (
                <MenuItem key={u.id} value={u.id}>
                  {userDisplayName(u)}
                </MenuItem>
              ))}
            </FilterSelect>
            <TextField
              size="small"
              type="date"
              label="Due date"
              value={assignDue}
              onChange={(e) => setAssignDue(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ minWidth: 160 }}
            />
            <Button
              variant="contained"
              disabled={!assignCourseId || !assignUserId || assignMutation.isPending}
              onClick={() => assignMutation.mutate()}
            >
              Assign & notify
            </Button>
          </Stack>
        </Box>

        {(allQuery.data ?? []).length > 0 ? (
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
              All open assignments
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Overdue items also appear on Process Audit.
            </Typography>
            <Stack spacing={0.5}>
              {(allQuery.data ?? [])
                .filter((row) => row.status !== 'completed')
                .slice(0, 40)
                .map((row) => (
                  <Typography key={row.id} variant="body2">
                    {row.course_title} · due {row.due_date || '—'} · status {row.status}
                  </Typography>
                ))}
            </Stack>
          </Box>
        ) : null}
      </Stack>
    </PageContainer>
  );
}
