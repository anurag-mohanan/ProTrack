import { useMemo, useState } from 'react';
import {
  Chip,
  Link,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import { apiClient } from '../api/client';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ContentCard } from '../components/ui/cards';

export type PastEmployee = {
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  designation: string | null;
  joining_date: string | null;
  leaving_date: string | null;
  is_archived: boolean;
  is_active: boolean;
  offboard_applied_at: string | null;
  has_left: boolean;
  team_names: string[];
  exit_interview_id: string | null;
  attitude_was_good: boolean | null;
  skillset_rating: number | null;
  eligible_for_rehire: string | null;
};

function rehireLabel(value: string | null): string {
  if (value === 'yes') return 'Yes';
  if (value === 'no') return 'No';
  if (value === 'conditional') return 'Conditional';
  return '—';
}

export default function PastEmployeesPage() {
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');

  const query = useQuery({
    queryKey: ['hr-past-employees', appliedSearch],
    queryFn: async () => {
      const params = appliedSearch.trim()
        ? `?search=${encodeURIComponent(appliedSearch.trim())}`
        : '';
      return (await apiClient.get<PastEmployee[]>(`/hr/past-employees${params}`)).data;
    },
  });

  const rows = query.data ?? [];
  const leftCount = useMemo(() => rows.filter((r) => r.has_left).length, [rows]);
  const noticeCount = useMemo(() => rows.filter((r) => !r.has_left).length, [rows]);

  return (
    <PageContainer>
      <PageHeader
        title="Past employees"
        subtitle="People with a last working day recorded. Soft-offboarded staff stay here with team history and exit assessment when available."
      />

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        sx={{ mb: 2, alignItems: { sm: 'center' } }}
      >
          <TextField
            size="small"
            label="Search name or email"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setAppliedSearch(search);
            }}
            sx={{ minWidth: 260 }}
          />
          <Chip
            size="small"
            label="Search"
            color="primary"
            variant="outlined"
            onClick={() => setAppliedSearch(search)}
            sx={{ cursor: 'pointer' }}
          />
          <Chip size="small" label={`${leftCount} left`} color="default" />
        <Chip size="small" label={`${noticeCount} on notice`} color="warning" variant="outlined" />
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          Exit interviews:{' '}
          <Link component={RouterLink} to="/hr/exit-process">
            Exit process
          </Link>
        </Typography>
      </Stack>

      {query.isLoading ? (
        <LoadingState message="Loading past employees…" />
      ) : (
        <ContentCard>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Employee</TableCell>
                  <TableCell>Designation</TableCell>
                  <TableCell>Teams (history)</TableCell>
                  <TableCell>Joined</TableCell>
                  <TableCell>Last working day</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Rehire</TableCell>
                  <TableCell>Skill</TableCell>
                  <TableCell>Exit interview</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9}>
                      <Typography color="text.secondary">
                        No past employees yet. Set a last working day on Admin Users / Finance People
                        Costs, or complete an exit interview for a linked employee.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  rows.map((row) => (
                    <TableRow key={row.user_id} hover>
                      <TableCell>
                        <Typography sx={{ fontWeight: 600 }}>
                          {row.first_name} {row.last_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {row.email}
                        </Typography>
                      </TableCell>
                      <TableCell>{row.designation || '—'}</TableCell>
                      <TableCell>
                        {row.team_names.length ? row.team_names.join(', ') : '—'}
                      </TableCell>
                      <TableCell>{row.joining_date || '—'}</TableCell>
                      <TableCell>{row.leaving_date || '—'}</TableCell>
                      <TableCell>
                        {row.has_left ? (
                          <Chip
                            size="small"
                            label={row.is_archived ? 'Left · archived' : 'Left'}
                            color="default"
                          />
                        ) : (
                          <Chip size="small" label="On notice" color="warning" variant="outlined" />
                        )}
                      </TableCell>
                      <TableCell>{rehireLabel(row.eligible_for_rehire)}</TableCell>
                      <TableCell>
                        {row.skillset_rating != null ? row.skillset_rating : '—'}
                      </TableCell>
                      <TableCell>
                        {row.exit_interview_id ? (
                          <Link
                            component={RouterLink}
                            to="/hr/exit-process"
                            underline="hover"
                          >
                            View
                          </Link>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </ContentCard>
      )}
    </PageContainer>
  );
}
