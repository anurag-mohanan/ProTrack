import { useEffect, useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import {
  fetchEmailTemplateVariables,
  previewEmailTemplate,
} from '../../api/communication';
import { fetchEmailTemplates, updateEmailTemplate } from '../../api/settings';
import { useToast } from '../../context/ToastContext';

const SAMPLE_CONTEXT: Record<string, string> = {
  Designer: 'Alex Morgan',
  Surfacer: 'Sam Rivera',
  DesignLeader: 'Jordan Lee',
  Customer: 'Acme Manufacturing',
  CustomerContact: 'Pat Chen',
  ToolNumber: 'T-24018',
  PartDescription: 'Injection mould core insert',
  ProjectStage: 'final',
  ProjectStatus: 'currently_being_worked_on',
  DueDate: '2026-07-15',
  Milestone: 'Final design review',
  QuotedHours: '120.00',
  ActualHours: '98.50',
  Variance: '-21.50',
  Company: 'Prosohm Engineering',
  Manager: 'Jordan Lee',
  Message: 'Sample preview message for template editing.',
};

export default function EmailTemplatesPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['settings', 'email-templates'], queryFn: fetchEmailTemplates });
  const variablesQuery = useQuery({
    queryKey: ['emails', 'variables'],
    queryFn: fetchEmailTemplateVariables,
  });
  const selected = query.data?.find((template) => template.id === selectedId) ?? query.data?.[0] ?? null;

  const [form, setForm] = useState({
    subject: '',
    body_html: '',
    body_text: '',
    is_enabled: true,
  });
  const [preview, setPreview] = useState<{ subject: string; body_html: string; body_text?: string | null } | null>(
    null,
  );

  useEffect(() => {
    if (selected) {
      setForm({
        subject: selected.subject,
        body_html: selected.body_html,
        body_text: selected.body_text ?? '',
        is_enabled: selected.is_enabled,
      });
      setPreview(null);
    }
  }, [selected?.id]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateEmailTemplate(selected!.id, {
        subject: form.subject,
        body_html: form.body_html,
        body_text: form.body_text || null,
        is_enabled: form.is_enabled,
      }),
    onSuccess: () => {
      showSuccess('Template saved');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'email-templates'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      previewEmailTemplate({
        subject: form.subject,
        body_html: form.body_html,
        body_text: form.body_text || null,
        context: SAMPLE_CONTEXT,
      }),
    onSuccess: (result) => setPreview(result),
    onError: (error: Error) => showError(error.message),
  });

  if (query.isLoading) return <LoadingState message="Loading email templates…" />;

  return (
    <Box>
      <PageHeader
        title="Email Templates"
        subtitle="Edit transactional, customer, and digest templates. Preview placeholders before saving."
      />
      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mb: 2 }}>
        {(variablesQuery.data ?? []).map((variable) => (
          <Chip key={variable} size="small" label={`{{${variable}}}`} variant="outlined" />
        ))}
      </Stack>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
        <Box sx={{ flex: 1 }}>
          <ContentCard title="Templates">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Slug</TableCell>
                  <TableCell>Enabled</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(query.data ?? []).map((template) => (
                  <TableRow
                    key={template.id}
                    hover
                    selected={selected?.id === template.id}
                    onClick={() => setSelectedId(template.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>{template.name}</TableCell>
                    <TableCell>{template.slug}</TableCell>
                    <TableCell>{template.is_enabled ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ContentCard>
        </Box>
        {selected ? (
          <Box sx={{ flex: 2 }}>
            <ContentCard title={selected.name}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {selected.description}
              </Typography>
              <Stack spacing={2}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={form.is_enabled}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, is_enabled: event.target.checked }))
                      }
                    />
                  }
                  label="Template enabled"
                />
                <TextField
                  label="Subject"
                  value={form.subject}
                  onChange={(event) => setForm((current) => ({ ...current, subject: event.target.value }))}
                />
                <TextField
                  label="HTML body"
                  value={form.body_html}
                  onChange={(event) => setForm((current) => ({ ...current, body_html: event.target.value }))}
                  multiline
                  minRows={8}
                />
                <TextField
                  label="Plain text body"
                  value={form.body_text}
                  onChange={(event) => setForm((current) => ({ ...current, body_text: event.target.value }))}
                  multiline
                  minRows={4}
                />
                <Stack direction="row" spacing={1}>
                  <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
                    Save Template
                  </ProsohmButton>
                  <ProsohmButton
                    buttonVariant="outlined"
                    onClick={() => previewMutation.mutate()}
                    loading={previewMutation.isPending}
                  >
                    Preview
                  </ProsohmButton>
                </Stack>
                {preview ? (
                  <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 2 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                      Preview: {preview.subject}
                    </Typography>
                    <Box dangerouslySetInnerHTML={{ __html: preview.body_html }} />
                  </Box>
                ) : null}
              </Stack>
            </ContentCard>
          </Box>
        ) : null}
      </Stack>
    </Box>
  );
}
