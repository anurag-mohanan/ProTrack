import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Box, Grid, TextField } from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { fetchCompanySettings, updateCompanySettings } from '../../api/settings';
import { useState, useEffect } from 'react';
import { useToast } from '../../context/ToastContext';

export default function CompanyProfilePage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings', 'company'], queryFn: fetchCompanySettings });
  const [form, setForm] = useState({
    company_name: '',
    address: '',
    phone: '',
    website: '',
    gst_number: '',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    financial_year_start_month: 4,
    default_working_hours_per_day: 8,
    default_working_days: 'Mon,Tue,Wed,Thu,Fri',
    logo_url: '',
  });

  useEffect(() => {
    if (query.data) {
      setForm({
        company_name: query.data.company_name,
        address: query.data.address ?? '',
        phone: query.data.phone ?? '',
        website: query.data.website ?? '',
        gst_number: query.data.gst_number ?? '',
        currency: query.data.currency,
        timezone: query.data.timezone,
        financial_year_start_month: query.data.financial_year_start_month,
        default_working_hours_per_day: Number(query.data.default_working_hours_per_day),
        default_working_days: query.data.default_working_days,
        logo_url: query.data.logo_url ?? '',
      });
    }
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () => updateCompanySettings(form),
    onSuccess: () => {
      showSuccess('Company profile saved');
      void queryClient.invalidateQueries({ queryKey: ['settings', 'company'] });
    },
    onError: (error) => showError(String(error)),
  });

  if (query.isLoading) return <LoadingState message="Loading company profile…" />;

  return (
    <Box>
      <PageHeader title="Company Profile" subtitle="Organisation identity and default working patterns" />
      <ContentCard title="Company information">
        <Grid container spacing={2}>
          {[
            ['company_name', 'Company Name'],
            ['logo_url', 'Logo URL'],
            ['address', 'Address'],
            ['phone', 'Phone'],
            ['website', 'Website'],
            ['gst_number', 'GST Number'],
            ['currency', 'Currency'],
            ['timezone', 'Timezone'],
            ['default_working_days', 'Default Working Days'],
          ].map(([key, label]) => (
            <Grid size={{ xs: 12, md: 6 }} key={key}>
              <TextField
                fullWidth
                label={label}
                value={String(form[key as keyof typeof form] ?? '')}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [key]: event.target.value }))
                }
              />
            </Grid>
          ))}
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              type="number"
              label="Financial Year Start Month"
              value={form.financial_year_start_month}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  financial_year_start_month: Number(event.target.value),
                }))
              }
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              type="number"
              label="Default Working Hours / Day"
              value={form.default_working_hours_per_day}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  default_working_hours_per_day: Number(event.target.value),
                }))
              }
            />
          </Grid>
        </Grid>
        <Box sx={{ mt: 3 }}>
          <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
            Save Company Profile
          </ProsohmButton>
        </Box>
      </ContentCard>
    </Box>
  );
}
