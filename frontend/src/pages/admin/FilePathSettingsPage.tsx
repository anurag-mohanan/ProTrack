import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, TextField } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchFilePathSettings, updateFilePathSettings } from '../../api/settings';
import { useEffect, useState } from 'react';
import { useToast } from '../../context/ToastContext';

export default function FilePathSettingsPage() {
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings', 'file-paths'], queryFn: fetchFilePathSettings });
  const [form, setForm] = useState({
    project_root_folder: '',
    customer_folder_template: '',
    drawing_folder_template: '',
    design_folder_template: '',
    backup_folder: '',
  });

  useEffect(() => {
    if (query.data) {
      setForm({
        project_root_folder: query.data.project_root_folder ?? '',
        customer_folder_template: query.data.customer_folder_template ?? '',
        drawing_folder_template: query.data.drawing_folder_template ?? '',
        design_folder_template: query.data.design_folder_template ?? '',
        backup_folder: query.data.backup_folder ?? '',
      });
    }
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () => updateFilePathSettings(form),
    onSuccess: () => {
      showSuccess('File path settings saved');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'file-paths'] });
    },
  });

  if (query.isLoading) return <LoadingState message="Loading file path settings…" />;

  return (
    <Box>
      <PageHeader title="File Path Settings" subtitle="Store folder templates only — no CAD uploads" />
      <ContentCard title="Folder templates">
        {Object.entries(form).map(([key, value]) => (
          <TextField
            key={key}
            fullWidth
            sx={{ mb: 2 }}
            label={key.replaceAll('_', ' ')}
            value={value ?? ''}
            onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
          />
        ))}
        <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
          Save Paths
        </ProsohmButton>
      </ContentCard>
    </Box>
  );
}
