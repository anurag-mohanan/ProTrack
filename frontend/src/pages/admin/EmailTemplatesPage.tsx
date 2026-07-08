import { useState } from 'react';
import {
  Box,
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
import { fetchEmailTemplates, updateEmailTemplate } from '../../api/settings';
import { useToast } from '../../context/ToastContext';

export default function EmailTemplatesPage() {
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['settings', 'email-templates'], queryFn: fetchEmailTemplates });
  const selected = query.data?.find((template) => template.id === selectedId) ?? query.data?.[0] ?? null;

  const [form, setForm] = useState({
    subject: '',
    body_html: '',
    body_text: '',
    is_enabled: true,
  });

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
  });

  if (query.isLoading) return <LoadingState message="Loading email templates…" />;

  return (
    <Box>
      <PageHeader
        title="Email Templates"
        subtitle="Edit transactional and manual email templates. Use placeholders like {{Designer}} and {{ToolNumber}}."
      />
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
                  onClick={() => {
                    setSelectedId(template.id);
                    setForm({
                      subject: template.subject,
                      body_html: template.body_html,
                      body_text: template.body_text ?? '',
                      is_enabled: template.is_enabled,
                    });
                  }}
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
              <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
                Save Template
              </ProsohmButton>
            </Stack>
          </ContentCard>
          </Box>
        ) : null}
      </Stack>
    </Box>
  );
}
