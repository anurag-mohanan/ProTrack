import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Button } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import AssignmentIndRoundedIcon from '@mui/icons-material/AssignmentIndRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import ConfirmationNumberRoundedIcon from '@mui/icons-material/ConfirmationNumberRounded';
import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
import PlaylistAddCheckRoundedIcon from '@mui/icons-material/PlaylistAddCheckRounded';
import { ticketsApi } from '../api/tickets';
import { PageContainer } from '../components/common/PageContainer';
import { KpiMetricCard, ModernPageHeader } from '../components/ui/design-system';
import { NewTicketDialog } from '../components/tickets/NewTicketDialog';
import { TicketQueue } from '../components/tickets/TicketQueue';
import { HELP_DESK_VIEWS } from '../components/tickets/ticketConstants';
import { useTicketCapabilities } from '../components/tickets/useTicketMeta';

export function HelpDeskPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const capabilities = useTicketCapabilities();
  const isAgent = Boolean(capabilities.data?.is_agent);
  const statsQuery = useQuery({ queryKey: ['tickets', 'stats'], queryFn: () => ticketsApi.stats() });
  const stats = statsQuery.data;

  const views = isAgent
    ? HELP_DESK_VIEWS
    : HELP_DESK_VIEWS.filter((view) => view.value === 'raised' || view.value === 'all');
  const defaultView = isAgent ? 'team' : 'raised';
  const currentView = searchParams.get('view') ?? defaultView;
  const currentStatus = searchParams.get('status') ?? '';

  const applyCard = (view: string, status = '') => {
    const next = new URLSearchParams();
    if (view !== defaultView) next.set('view', view);
    if (status) next.set('status', status);
    setSearchParams(next, { replace: true });
  };

  return (
    <PageContainer>
      <ModernPageHeader
        title="Help Desk"
        subtitle="Raise and track IT, facility, administration and HR requests."
        actions={
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreateOpen(true)}>
            New ticket
          </Button>
        }
        summary={
          <Box
            sx={{
              display: 'grid',
              gap: 1.5,
              gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', md: 'repeat(5, 1fr)' },
            }}
          >
            <KpiMetricCard
              title="Raised by me"
              value={String(stats?.raised_by_me ?? 0)}
              icon={ConfirmationNumberRoundedIcon}
              compact
              onClick={() => applyCard('raised')}
              selected={currentView === 'raised' && !currentStatus}
            />
            {isAgent ? (
              <KpiMetricCard
                title="Assigned to me"
                value={String(stats?.assigned_to_me ?? 0)}
                icon={AssignmentIndRoundedIcon}
                accent="warning"
                compact
                onClick={() => applyCard('mine')}
                selected={currentView === 'mine'}
              />
            ) : null}
            <KpiMetricCard
              title="Active"
              value={String(stats?.active ?? 0)}
              icon={PlaylistAddCheckRoundedIcon}
              accent="info"
              compact
              onClick={() => applyCard(isAgent ? 'team' : 'all', 'active')}
              selected={currentStatus === 'active'}
            />
            <KpiMetricCard
              title="Waiting"
              value={String(stats?.pending ?? 0)}
              icon={HourglassEmptyRoundedIcon}
              accent="warning"
              compact
              onClick={() => applyCard('all', 'waiting')}
              selected={currentStatus === 'waiting'}
            />
            <KpiMetricCard
              title="Resolved"
              value={String(stats?.resolved ?? 0)}
              icon={CheckCircleRoundedIcon}
              accent="success"
              compact
              onClick={() => applyCard('all', 'resolved')}
              selected={currentStatus === 'resolved'}
            />
          </Box>
        }
      />

      {capabilities.isLoading ? null : (
        <TicketQueue
          views={views}
          defaultView={defaultView}
          emptyHint="Change the view or filters, or raise a new ticket."
        />
      )}

      <NewTicketDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(ticket) => {
          setCreateOpen(false);
          const next = new URLSearchParams(searchParams);
          next.set('ticket', ticket.id);
          setSearchParams(next);
        }}
      />
    </PageContainer>
  );
}

export default HelpDeskPage;
