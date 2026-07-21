import { useMemo } from 'react';
import { Box, Chip, MenuItem, Stack, TextField, Typography } from '@mui/material';
import ContactPhoneIcon from '@mui/icons-material/ContactPhone';
import SupportAgentRoundedIcon from '@mui/icons-material/SupportAgentRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { ticketsApi, usersApi } from '../../api/resources';

export default function TicketRoutingPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const routesQuery = useQuery({
    queryKey: ['ticket-routes'],
    queryFn: () => ticketsApi.listRoutes(),
  });

  const usersQuery = useQuery({
    queryKey: ['users', 'active-lite'],
    queryFn: () => usersApi.list({ limit: 500 }),
  });

  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? [])
        .map((user) => ({
          id: user.id,
          name: `${user.first_name} ${user.last_name}`.trim(),
        }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [usersQuery.data],
  );

  const setRouteMutation = useMutation({
    mutationFn: ({ category, assigneeId }: { category: string; assigneeId: string | null }) =>
      ticketsApi.setRoute(category, { assignee_user_id: assigneeId }),
    onSuccess: () => {
      showSuccess('Help desk routing updated.');
      void queryClient.invalidateQueries({ queryKey: ['ticket-routes'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  const routes = routesQuery.data ?? [];

  if (routesQuery.isLoading) return <LoadingState message="Loading help desk routing…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Help Desk Routing"
        subtitle="Nominate the person who receives each ticket category. New tickets in that category are automatically assigned to them, and they can work the queue regardless of their role. Leave blank to fall back to the default role-based queues below."
      />

      <Stack spacing={1.5}>
        {routes.map((route) => (
          <ContentCard key={route.category} noPadding>
            <Box
              sx={{
                px: 2,
                py: 1.75,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
                flexWrap: 'wrap',
              }}
            >
              <Box sx={{ minWidth: 220, flex: '1 1 260px' }}>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                  <SupportAgentRoundedIcon fontSize="small" color="primary" />
                  <Typography sx={{ fontWeight: 800 }}>{route.category_label}</Typography>
                </Stack>
                <Typography variant="caption" color="text.secondary" component="div">
                  {route.assignee_user_id
                    ? `Tickets auto-assign to ${route.assignee_name ?? 'the selected contact'}.`
                    : 'No contact set — falls back to the default queue:'}
                </Typography>
                {!route.assignee_user_id && route.fallback_roles.length > 0 ? (
                  <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                    {route.fallback_roles.map((role) => (
                      <Chip key={role} label={role} size="small" variant="outlined" />
                    ))}
                  </Stack>
                ) : null}
              </Box>

              <TextField
                select
                size="small"
                label="Contact / owner"
                value={route.assignee_user_id ?? ''}
                onChange={(event) =>
                  setRouteMutation.mutate({
                    category: route.category,
                    assigneeId: event.target.value || null,
                  })
                }
                disabled={setRouteMutation.isPending}
                sx={{ minWidth: 260, flex: '0 0 auto' }}
              >
                <MenuItem value="">— Use default queue —</MenuItem>
                {userOptions.map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {user.name}
                  </MenuItem>
                ))}
              </TextField>
            </Box>
          </ContentCard>
        ))}
      </Stack>

      <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <ContactPhoneIcon fontSize="small" color="disabled" />
        <Typography variant="caption" color="text.secondary">
          Requesters always keep visibility of their own tickets. Admins and executives can see and
          manage every category.
        </Typography>
      </Box>
    </PageContainer>
  );
}
