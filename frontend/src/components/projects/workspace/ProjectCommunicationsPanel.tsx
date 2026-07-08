import { useState } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ProsohmButton } from '../../ui/ProsohmButton';
import {
  fetchProjectCommunications,
  sendCustomerEmail,
  sendOneClickEmail,
} from '../../../api/communication';
import type { EmailMessage } from '../../../api/communication';
import { useToast } from '../../../context/ToastContext';
import { ROLES } from '../../../utils/permissions';
import { useAuth } from '../../../context/AuthContext';

const ONE_CLICK_ACTIONS = [
  { action: 'notify_designer', label: 'Notify Designer' },
  { action: 'notify_customer', label: 'Notify Customer' },
  { action: 'notify_team', label: 'Notify Team' },
  { action: 'request_update', label: 'Request Update' },
  { action: 'request_review', label: 'Request Review' },
  { action: 'send_release', label: 'Send Release' },
] as const;

const CUSTOMER_TEMPLATES = [
  { slug: 'project_status', label: 'Project Status' },
  { slug: 'progress_update', label: 'Progress Update' },
  { slug: 'files_released', label: 'Files Released' },
  { slug: 'delay_notification', label: 'Delay Notification' },
  { slug: 'meeting_summary', label: 'Meeting Summary' },
  { slug: 'quote', label: 'Quote' },
  { slug: 'engineering_change_notice', label: 'Engineering Change Notice' },
] as const;

interface ProjectCommunicationsPanelProps {
  projectId: string;
}

export function ProjectCommunicationsPanel({ projectId }: ProjectCommunicationsPanelProps) {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const [selected, setSelected] = useState<EmailMessage | null>(null);
  const [customerTemplate, setCustomerTemplate] = useState<string>(CUSTOMER_TEMPLATES[0].slug);

  const canSend = (
    [
      ROLES.ADMIN,
      ROLES.ENGINEERING_MANAGER,
      ROLES.DESIGN_LEADER,
      ROLES.PROJECT_MANAGER,
    ] as string[]
  ).includes(user?.role_name ?? '');

  const query = useQuery({
    queryKey: ['project-communications', projectId, search],
    queryFn: () => fetchProjectCommunications(projectId, search || undefined),
  });

  const oneClickMutation = useMutation({
    mutationFn: (action: string) =>
      sendOneClickEmail({
        project_id: projectId,
        action,
        message,
        attach_released_files: action === 'send_release',
      }),
    onSuccess: () => {
      showSuccess('Email sent');
      void query.refetch();
    },
    onError: (error: Error) => showError(error.message),
  });

  const customerMutation = useMutation({
    mutationFn: () =>
      sendCustomerEmail({
        project_id: projectId,
        template_slug: customerTemplate,
        message,
      }),
    onSuccess: () => {
      showSuccess('Customer email sent');
      void query.refetch();
    },
    onError: (error: Error) => showError(error.message),
  });

  return (
    <Box>
      {canSend ? (
        <Stack spacing={2} sx={{ mb: 3 }}>
          <TextField
            label="Message (optional)"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            multiline
            minRows={2}
            fullWidth
          />
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
            {ONE_CLICK_ACTIONS.map((item) => (
              <ProsohmButton
                key={item.action}
                buttonVariant="outlined"
                size="small"
                onClick={() => oneClickMutation.mutate(item.action)}
                loading={oneClickMutation.isPending}
              >
                {item.label}
              </ProsohmButton>
            ))}
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ alignItems: 'center' }}>
            <TextField
              select
              size="small"
              label="Customer template"
              value={customerTemplate}
              onChange={(event) => setCustomerTemplate(event.target.value)}
              sx={{ minWidth: 220 }}
            >
              {CUSTOMER_TEMPLATES.map((item) => (
                <MenuItem key={item.slug} value={item.slug}>
                  {item.label}
                </MenuItem>
              ))}
            </TextField>
            <ProsohmButton
              buttonVariant="outlined"
              onClick={() => customerMutation.mutate()}
              loading={customerMutation.isPending}
            >
              Send Customer Email
            </ProsohmButton>
          </Stack>
        </Stack>
      ) : null}

      <TextField
        size="small"
        label="Search communications"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        sx={{ mb: 2, maxWidth: 360 }}
      />

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Date</TableCell>
            <TableCell>Recipient</TableCell>
            <TableCell>Subject</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Attachments</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {(query.data ?? []).map((entry: EmailMessage) => (
            <TableRow
              key={entry.id}
              hover
              sx={{ cursor: 'pointer' }}
              onClick={() => setSelected(entry)}
            >
              <TableCell>{new Date(entry.sent_at ?? entry.created_at).toLocaleString()}</TableCell>
              <TableCell>{entry.recipients_display}</TableCell>
              <TableCell>{entry.subject}</TableCell>
              <TableCell>
                <Chip size="small" label={entry.status} />
              </TableCell>
              <TableCell>{entry.attachments.length || '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {(query.data ?? []).length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          No communication history for this project yet.
        </Typography>
      ) : null}

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} maxWidth="md" fullWidth>
        <DialogTitle>{selected?.subject}</DialogTitle>
        <DialogContent>
          {selected ? (
            <Box
              sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 2 }}
              dangerouslySetInnerHTML={{ __html: selected.body_html }}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
