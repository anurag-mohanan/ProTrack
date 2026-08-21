import { useEffect, useState, type FormEvent } from 'react';
import { Box, Stack, Alert, Typography } from '@mui/material';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchItSettings,
  itOperationsKeys,
  updateItSettings,
} from '../../api/itOperations';
import { getErrorMessage } from '../../api/client';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { FormField, FormSelect } from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { ITSettingsUpdate } from '../../types/itOperations';
import { optionalString } from '../../utils/formValues';
import {
  accessContextFromUser,
  canManageItDataImports,
  canManageItSettings,
} from '../../utils/permissions';
import { ITMigrationPanel } from '../../components/it/ITMigrationPanel';

type SettingsFormState = {
  asset_numbering_pattern: string;
  computer_naming_pattern: string;
  default_domain: string;
  default_email_domain: string;
  ip_allocation_strategy: string;
};

const emptyForm: SettingsFormState = {
  asset_numbering_pattern: '',
  computer_naming_pattern: '',
  default_domain: '',
  default_email_domain: '',
  ip_allocation_strategy: 'sequential',
};

const STRATEGY_OPTIONS = [
  { value: 'sequential', label: 'Sequential' },
  { value: 'manual', label: 'Manual' },
];

export function ITSettingsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canManage = canManageItSettings(accessContextFromUser(user));
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SettingsFormState>(emptyForm);

  const query = useQuery({
    queryKey: itOperationsKeys.settings(),
    queryFn: fetchItSettings,
    enabled: canManage,
  });

  useEffect(() => {
    if (!query.data) return;
    setForm({
      asset_numbering_pattern: query.data.asset_numbering_pattern ?? '',
      computer_naming_pattern: query.data.computer_naming_pattern ?? '',
      default_domain: query.data.default_domain ?? '',
      default_email_domain: query.data.default_email_domain ?? '',
      ip_allocation_strategy: query.data.ip_allocation_strategy || 'sequential',
    });
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: ITSettingsUpdate) => updateItSettings(payload),
    onSuccess: () => {
      showSuccess('IT settings saved.');
      void queryClient.invalidateQueries({ queryKey: itOperationsKeys.settings() });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const handleSave = (event?: FormEvent) => {
    event?.preventDefault();
    saveMutation.mutate({
      asset_numbering_pattern: form.asset_numbering_pattern.trim(),
      computer_naming_pattern: form.computer_naming_pattern.trim(),
      default_domain: optionalString(form.default_domain),
      default_email_domain: optionalString(form.default_email_domain),
      ip_allocation_strategy: form.ip_allocation_strategy,
    });
  };

  if (!canManage) {
    return (
      <PageContainer>
        <PageHeader title="IT Settings" subtitle="Naming and allocation conventions." />
        <ErrorState error={new Error('You do not have permission to manage IT settings.')} />
      </PageContainer>
    );
  }

  if (query.isLoading) {
    return <LoadingState message="Loading IT settings…" />;
  }

  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        title="Unable to load IT settings"
        onRetry={() => void query.refetch()}
      />
    );
  }

  return (
    <PageContainer>
      <PageHeader
        title="IT Settings"
        subtitle="Configure asset numbering, computer naming, and IP allocation."
        action={
          <ProsohmButton
            buttonVariant="primary"
            startIcon={<SettingsRoundedIcon />}
            loading={saveMutation.isPending}
            onClick={() => handleSave()}
          >
            Save settings
          </ProsohmButton>
        }
      />

      <ContentCard title="Conventions">
        <Box
          component="form"
          onSubmit={handleSave}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, maxWidth: 640 }}
        >
          <FormField
            label="Asset numbering pattern"
            value={form.asset_numbering_pattern}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                asset_numbering_pattern: event.target.value,
              }))
            }
            helper="Example: {prefix}-{seq:04d}"
          />
          <FormField
            label="Computer naming pattern"
            value={form.computer_naming_pattern}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                computer_naming_pattern: event.target.value,
              }))
            }
            helper="Example: {org}-{type}{seq:03d}"
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <FormField
              label="Default domain"
              value={form.default_domain}
              onChange={(event) =>
                setForm((current) => ({ ...current, default_domain: event.target.value }))
              }
              sx={{ flex: 1 }}
            />
            <FormField
              label="Default email domain"
              value={form.default_email_domain}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  default_email_domain: event.target.value,
                }))
              }
              sx={{ flex: 1 }}
            />
          </Stack>
          <FormSelect
            label="IP allocation strategy"
            value={form.ip_allocation_strategy}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                ip_allocation_strategy: String(event.target.value),
              }))
            }
            options={STRATEGY_OPTIONS}
          />
        </Box>
      </ContentCard>

      <Box sx={{ mt: 3 }}>
        <ContentCard title="Data Import">
          <Stack spacing={1.5}>
            <Alert severity="info">
              Use the sequential IT Data Import center for the split workbooks (
              01_Assets.xlsx … 08_Migration_Exceptions.xlsx). Preview each file before commit.
            </Alert>
            {canManageItDataImports(accessContextFromUser(user)) ? (
              <ProsohmButton
                buttonVariant="outlined"
                onClick={() => navigate('/it/data-import')}
              >
                Open IT Data Import
              </ProsohmButton>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Manage IT Data Imports permission is required.
              </Typography>
            )}
            <Typography variant="subtitle2" sx={{ pt: 1 }}>
              Legacy multi-sheet migration (optional)
            </Typography>
            <ITMigrationPanel />
          </Stack>
        </ContentCard>
      </Box>
    </PageContainer>
  );
}
