import { useEffect, useMemo, useState } from 'react';
import { Box, Grid, MenuItem } from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { FormField, FormSection } from '../../components/ui/design-system';
import { LogoUpload } from '../../components/settings/LogoUpload';
import {
  fetchCompanySettings,
  updateCompanySettings,
  uploadCompanyLogo,
} from '../../api/settings';
import { useToast } from '../../context/ToastContext';

const TIMEZONES = [
  'Asia/Kolkata',
  'Asia/Singapore',
  'Europe/London',
  'America/New_York',
  'America/Chicago',
  'UTC',
];

const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD'];

const WORKING_DAY_OPTIONS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function CompanyProfilePage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings', 'company'], queryFn: fetchCompanySettings });
  const [form, setForm] = useState({
    company_name: '',
    company_short_name: '',
    email: '',
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
  const [selectedDays, setSelectedDays] = useState<string[]>([]);

  useEffect(() => {
    if (query.data) {
      setForm({
        company_name: query.data.company_name,
        company_short_name: query.data.company_short_name ?? '',
        email: query.data.email ?? '',
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
      setSelectedDays(query.data.default_working_days.split(',').filter(Boolean));
    }
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateCompanySettings({
        ...form,
        default_working_days: selectedDays.join(','),
      }),
    onSuccess: async () => {
      showSuccess('Company information saved');
      await queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (error) => showError(String(error)),
  });

  const logoMutation = useMutation({
    mutationFn: uploadCompanyLogo,
    onSuccess: async (data) => {
      setForm((current) => ({ ...current, logo_url: data.logo_url ?? '' }));
      showSuccess('Company logo updated');
      await queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (error) => showError(String(error)),
  });

  const financialYearLabel = useMemo(() => {
    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
    ];
    return monthNames[form.financial_year_start_month - 1] ?? 'April';
  }, [form.financial_year_start_month]);

  if (query.isLoading) return <LoadingState message="Loading company information…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Company Information"
        subtitle="Organisation identity, branding inputs, and default working patterns"
      />

      <Grid container spacing={2.5}>
        <Grid size={{ xs: 12, lg: 4 }}>
          <ContentCard title="Company Logo">
            <LogoUpload
              logoUrl={form.logo_url}
              uploading={logoMutation.isPending}
              onUpload={async (file) => {
                await logoMutation.mutateAsync(file);
              }}
            />
          </ContentCard>
        </Grid>

        <Grid size={{ xs: 12, lg: 8 }}>
          <ContentCard title="Organisation Details">
            <FormSection title="Identity">
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    label="Company Name"
                    value={form.company_name}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, company_name: event.target.value }))
                    }
                    required
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    label="Short Company Name"
                    value={form.company_short_name}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, company_short_name: event.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    label="Email"
                    type="email"
                    value={form.email}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, email: event.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    label="Phone"
                    value={form.phone}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, phone: event.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    label="Website"
                    value={form.website}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, website: event.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    label="GST Number"
                    value={form.gst_number}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, gst_number: event.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <FormField
                    label="Address"
                    value={form.address}
                    multiline
                    minRows={3}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, address: event.target.value }))
                    }
                  />
                </Grid>
              </Grid>
            </FormSection>

            <FormSection title="Regional Settings">
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 4 }}>
                  <FormField
                    select
                    label="Currency"
                    value={form.currency}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, currency: event.target.value }))
                    }
                  >
                    {CURRENCIES.map((currency) => (
                      <MenuItem key={currency} value={currency}>
                        {currency}
                      </MenuItem>
                    ))}
                  </FormField>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                  <FormField
                    select
                    label="Timezone"
                    value={form.timezone}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, timezone: event.target.value }))
                    }
                  >
                    {TIMEZONES.map((timezone) => (
                      <MenuItem key={timezone} value={timezone}>
                        {timezone}
                      </MenuItem>
                    ))}
                  </FormField>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                  <FormField
                    type="number"
                    label="Financial Year Starts"
                    value={form.financial_year_start_month}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        financial_year_start_month: Number(event.target.value),
                      }))
                    }
                    helper={`Currently set to ${financialYearLabel}`}
                  />
                </Grid>
              </Grid>
            </FormSection>

            <FormSection title="Working Pattern">
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormField
                    type="number"
                    label="Working Hours / Day"
                    value={form.default_working_hours_per_day}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        default_working_hours_per_day: Number(event.target.value),
                      }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, pt: 1 }}>
                    {WORKING_DAY_OPTIONS.map((day) => {
                      const active = selectedDays.includes(day);
                      return (
                        <ProsohmButton
                          key={day}
                          size="small"
                          buttonVariant={active ? 'primary' : 'outlined'}
                          onClick={() =>
                            setSelectedDays((current) =>
                              current.includes(day)
                                ? current.filter((value) => value !== day)
                                : [...current, day],
                            )
                          }
                        >
                          {day}
                        </ProsohmButton>
                      );
                    })}
                  </Box>
                </Grid>
              </Grid>
            </FormSection>

            <Box sx={{ mt: 3 }}>
              <ProsohmButton onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
                Save Company Information
              </ProsohmButton>
            </Box>
          </ContentCard>
        </Grid>
      </Grid>
    </PageContainer>
  );
}
