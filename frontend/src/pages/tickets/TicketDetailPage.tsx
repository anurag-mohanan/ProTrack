import { Link as RouterLink, useParams } from 'react-router-dom';
import { Button, Paper } from '@mui/material';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { PageContainer } from '../../components/common/PageContainer';
import { ModernPageHeader } from '../../components/ui/design-system';
import { TicketDetailView } from '../../components/tickets/TicketDetailView';
import { useTicketCapabilities } from '../../components/tickets/useTicketMeta';

export default function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const capabilities = useTicketCapabilities();
  const backTo = capabilities.data?.manageable_categories.includes('it') ? '/it/requests' : '/help-desk';
  return (
    <PageContainer>
      <ModernPageHeader
        title="Ticket"
        subtitle="Request, owner, related records, conversation and full history."
        actions={
          <Button component={RouterLink} to={backTo} startIcon={<ArrowBackRoundedIcon />}>
            Back to queue
          </Button>
        }
      />
      <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2.5 } }}>
        {ticketId ? <TicketDetailView ticketId={ticketId} /> : null}
      </Paper>
    </PageContainer>
  );
}
