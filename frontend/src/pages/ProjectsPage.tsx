import { useMemo, useState } from 'react';
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
    const term = search.trim().toLowerCase();
    if (!term) return projectsQuery.data ?? [];

    return (projectsQuery.data ?? []).filter((project) => {
      const haystack = [project.tool_number, project.part_description]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [projectsQuery.data, search]);

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
                  if (value === 'active') {
                    searchParams.delete('lifecycle');
                    setSearchParams(searchParams);
                  } else {
                    setSearchParams({ lifecycle: value });
                  }
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
