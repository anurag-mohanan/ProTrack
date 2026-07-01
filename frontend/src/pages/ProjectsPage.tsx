import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchCustomers, fetchStreams, fetchUsers } from '../api/lookups';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectTable } from '../components/projects/ProjectTable';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { PageHeader } from '../components/common/PageHeader';
import { TableSkeleton } from '../components/common/TableSkeleton';
import { ContentCard } from '../components/ui/cards';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { QUERY_STALE_TIMES } from '../config/queryConfig';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  archiveProject,
  getProjects,
  projectQueryKeys,
} from '../services/projectService';
import type { ProjectLifecycleFilter, ProjectStatus } from '../types';
import { canArchiveProject } from '../utils/permissions';

const lifecycleOptions: Array<{ value: ProjectLifecycleFilter; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
  { value: 'deleted', label: 'Deleted' },
];

const statusOptions: Array<{ value: ProjectStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All Statuses' },
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'waiting_for_customer', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
];

export function ProjectsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | 'all'>('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [archiveId, setArchiveId] = useState<string | null>(null);

  const lifecycle =
    (searchParams.get('lifecycle') as ProjectLifecycleFilter | null) ?? 'active';
  const dueFilter = searchParams.get('due');
  const completedFilter = searchParams.get('completed');

  useEffect(() => {
    const status = searchParams.get('status');
    if (
      status &&
      statusOptions.some((option) => option.value === status)
    ) {
      setStatusFilter(status as ProjectStatus);
    } else if (!status) {
      setStatusFilter('all');
    }
  }, [searchParams]);

  const statusParam = statusFilter === 'all' ? undefined : statusFilter;

  const projectsQuery = useQuery({
    queryKey: projectQueryKeys.list({ lifecycle, status: statusParam }),
    queryFn: () =>
      getProjects({
        lifecycle,
        status: statusParam,
        limit: 500,
      }),
    staleTime: QUERY_STALE_TIMES.projects,
  });

  const archiveMutation = useMutation({
    mutationFn: archiveProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all });
      showSuccess('Project archived');
      setArchiveId(null);
    },
    onError: (error: Error) => showError(error.message),
  });

  const customersQuery = useQuery({
    queryKey: ['lookups', 'customers'],
    queryFn: fetchCustomers,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: fetchUsers,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const streamsQuery = useQuery({
    queryKey: ['lookups', 'streams'],
    queryFn: fetchStreams,
    staleTime: QUERY_STALE_TIMES.lookups,
  });

  const filteredProjects = useMemo(() => {
    let rows = projectsQuery.data ?? [];
    const term = search.trim().toLowerCase();
    if (term) {
      rows = rows.filter((project) => {
        const haystack = [project.tool_number, project.part_description]
          .join(' ')
          .toLowerCase();
        return haystack.includes(term);
      });
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (dueFilter === 'week' || dueFilter === '7days') {
      const rangeStart = new Date(today);
      if (dueFilter === 'week') {
        const day = rangeStart.getDay();
        const diff = day === 0 ? -6 : 1 - day;
        rangeStart.setDate(rangeStart.getDate() + diff);
      }
      const rangeEnd = new Date(rangeStart);
      rangeEnd.setDate(
        rangeEnd.getDate() + (dueFilter === 'week' ? 6 : 7),
      );

      rows = rows.filter((project) => {
        if (!project.due_date || project.status === 'completed') return false;
        const due = new Date(`${project.due_date}T00:00:00`);
        return due >= rangeStart && due <= rangeEnd;
      });
    }

    if (dueFilter === 'overdue') {
      rows = rows.filter((project) => {
        if (!project.due_date || project.status === 'completed') return false;
        return new Date(`${project.due_date}T00:00:00`) < today;
      });
    }

    if (completedFilter === 'month') {
      const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
      rows = rows.filter((project) => {
        if (project.status !== 'completed' || !project.completed_at) return false;
        const completed = new Date(project.completed_at);
        return completed >= monthStart && completed <= today;
      });
    }

    return rows;
  }, [projectsQuery.data, search, dueFilter, completedFilter]);

  const tableLoading =
    projectsQuery.isPending ||
    customersQuery.isPending ||
    usersQuery.isPending ||
    streamsQuery.isPending;

  const showArchiveActions =
    lifecycle !== 'archived' &&
    lifecycle !== 'deleted' &&
    canArchiveProject(user?.role_name ?? '');

  if (projectsQuery.error) return <ErrorState error={projectsQuery.error} />;
  if (customersQuery.error) return <ErrorState error={customersQuery.error} />;
  if (usersQuery.error) return <ErrorState error={usersQuery.error} />;
  if (streamsQuery.error) return <ErrorState error={streamsQuery.error} />;

  return (
    <Box>
      <PageHeader
        title="Projects"
        subtitle="Manage engineering projects and assignments"
        action={
          lifecycle === 'active' ? (
            <ProsohmButton
              buttonVariant="primary"
              startIcon={<AddIcon />}
              onClick={() => setCreateOpen(true)}
            >
              Create Project
            </ProsohmButton>
          ) : undefined
        }
      />

      <Box sx={{ mb: 2.5 }}>
        <ContentCard>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <TextField
              label="Search tool number or description"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              sx={{ minWidth: 280, flex: 1 }}
            />
            <FormControl sx={{ minWidth: 180 }}>
              <InputLabel>Lifecycle</InputLabel>
              <Select
                label="Lifecycle"
                value={lifecycle}
                onChange={(event) => {
                  const value = event.target.value as ProjectLifecycleFilter;
                  const next = new URLSearchParams(searchParams);
                  if (value === 'active') {
                    next.delete('lifecycle');
                  } else {
                    next.set('lifecycle', value);
                  }
                  setSearchParams(next);
                }}
              >
                {lifecycleOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl sx={{ minWidth: 220 }}>
              <InputLabel>Status</InputLabel>
              <Select
                label="Status"
                value={statusFilter}
                onChange={(event) => {
                  const value = event.target.value as ProjectStatus | 'all';
                  setStatusFilter(value);
                  const next = new URLSearchParams(searchParams);
                  if (value === 'all') {
                    next.delete('status');
                  } else {
                    next.set('status', value);
                  }
                  setSearchParams(next);
                }}
              >
                {statusOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </ContentCard>
      </Box>

      {tableLoading ? (
        <ContentCard noPadding>
          <TableSkeleton rows={10} columns={8} />
        </ContentCard>
      ) : !filteredProjects.length ? (
        <EmptyState
          title="No projects found"
          description="Try adjusting your search or filters, or create a new project."
        />
      ) : (
        <ContentCard noPadding>
          <ProjectTable
            projects={filteredProjects}
            customers={customersQuery.data ?? []}
            users={usersQuery.data ?? []}
            streams={streamsQuery.data ?? []}
            onArchive={
              showArchiveActions ? (projectId) => setArchiveId(projectId) : undefined
            }
          />
        </ContentCard>
      )}

      <ProjectFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(projectId) => navigate(`/projects/${projectId}`)}
      />

      <ConfirmDialog
        open={archiveId !== null}
        title="Archive project?"
        message="Archived projects are removed from the default list but remain in reports and history."
        confirmLabel="Archive"
        loading={archiveMutation.isPending}
        onClose={() => setArchiveId(null)}
        onConfirm={() => archiveId && archiveMutation.mutate(archiveId)}
      />
    </Box>
  );
}
