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
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchCustomers, fetchStreams, fetchUsers } from '../api/lookups';
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog';
import { ProjectTable } from '../components/projects/ProjectTable';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageHeader } from '../components/common/PageHeader';
import { ContentCard } from '../components/ui/cards';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import { getProjects, projectQueryKeys } from '../services/projectService';
import type { ProjectStatus } from '../types';

const statusOptions: Array<{ value: ProjectStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All Statuses' },
  { value: 'not_started', label: 'Not Started' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'waiting_for_customer', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
];

export function ProjectsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | 'all'>('all');
  const [createOpen, setCreateOpen] = useState(false);

  const statusParam = statusFilter === 'all' ? undefined : statusFilter;

  const projectsQuery = useQuery({
    queryKey: projectQueryKeys.list(statusParam),
    queryFn: () =>
      getProjects(
        statusParam
          ? { status: statusParam, limit: 500 }
          : { limit: 500 },
      ),
  });

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: fetchCustomers,
  });

  const usersQuery = useQuery({
    queryKey: ['users'],
    queryFn: fetchUsers,
  });

  const streamsQuery = useQuery({
    queryKey: ['streams'],
    queryFn: fetchStreams,
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

  const isLoading =
    projectsQuery.isLoading ||
    customersQuery.isLoading ||
    usersQuery.isLoading ||
    streamsQuery.isLoading;

  if (isLoading) return <LoadingState message="Loading projects…" />;

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
          <ProsohmButton
            buttonVariant="primary"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Create Project
          </ProsohmButton>
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

      {!filteredProjects.length ? (
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
          />
        </ContentCard>
      )}

      <ProjectFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(projectId) => navigate(`/projects/${projectId}`)}
      />
    </Box>
  );
}
