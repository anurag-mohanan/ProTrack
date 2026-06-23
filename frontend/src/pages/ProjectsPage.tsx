import { useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
import { Link } from 'react-router-dom';
import { fetchCustomers, fetchUsers } from '../api/lookups';
import { fetchProjects } from '../api/projects';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { HealthChip, StatusChip } from '../components/common/StatusChip';
import { LoadingState } from '../components/common/LoadingState';
import type { ProjectStatus } from '../types';
import { formatNumber, userDisplayName } from '../utils/format';

const statusOptions: Array<{ value: ProjectStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All Statuses' },
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'waiting_for_customer', label: 'Waiting for Customer' },
  { value: 'completed', label: 'Completed' },
];

export function ProjectsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | 'all'>('all');

  const projectsQuery = useQuery({
    queryKey: ['projects', statusFilter === 'all' ? undefined : statusFilter],
    queryFn: () =>
      fetchProjects(statusFilter === 'all' ? undefined : { status: statusFilter }),
  });

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
  });

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  });

  const customerMap = useMemo(() => {
    const map = new Map<string, string>();
    customersQuery.data?.forEach((customer) => map.set(customer.id, customer.name));
    return map;
  }, [customersQuery.data]);

  const userMap = useMemo(() => {
    const map = new Map<string, string>();
    usersQuery.data?.forEach((user) => map.set(user.id, userDisplayName(user)));
    return map;
  }, [usersQuery.data]);

  const filteredProjects = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return projectsQuery.data ?? [];
    return (projectsQuery.data ?? []).filter((project) => {
      const haystack = [
        project.tool_number,
        project.part_description,
        project.code,
        customerMap.get(project.customer_id) ?? '',
        userMap.get(project.design_leader_id) ?? '',
        userMap.get(project.designer_id ?? '') ?? '',
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [projectsQuery.data, search, customerMap, userMap]);

  if (projectsQuery.isLoading || customersQuery.isLoading || usersQuery.isLoading) {
    return <LoadingState />;
  }

  if (projectsQuery.error) return <ErrorState error={projectsQuery.error} />;

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        Projects
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Search and filter the project portfolio
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <TextField
          label="Search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1 }}
        />
        <FormControl sx={{ minWidth: 220 }}>
          <InputLabel>Status</InputLabel>
          <Select
            label="Status"
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as ProjectStatus | 'all')
            }
          >
            {statusOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {!filteredProjects.length ? (
        <EmptyState title="No projects found" description="Try adjusting your search or filters." />
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Tool Number</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Design Leader</TableCell>
                <TableCell>Designer</TableCell>
                <TableCell align="right">Quoted Hours</TableCell>
                <TableCell align="right">Actual Hours</TableCell>
                <TableCell>Health</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredProjects.map((project) => (
                <TableRow key={project.id} hover>
                  <TableCell>
                    <Link to={`/projects/${project.id}`}>{project.tool_number}</Link>
                  </TableCell>
                  <TableCell>{project.part_description}</TableCell>
                  <TableCell>{customerMap.get(project.customer_id) ?? '—'}</TableCell>
                  <TableCell>
                    <StatusChip status={project.status} />
                  </TableCell>
                  <TableCell>{userMap.get(project.design_leader_id) ?? '—'}</TableCell>
                  <TableCell>
                    {project.designer_id ? userMap.get(project.designer_id) ?? '—' : '—'}
                  </TableCell>
                  <TableCell align="right">{formatNumber(project.quoted_hours)}</TableCell>
                  <TableCell align="right">{formatNumber(project.actual_hours)}</TableCell>
                  <TableCell>
                    <HealthChip health={project.health} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
