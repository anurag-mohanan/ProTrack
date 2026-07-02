import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  Grid,
  MenuItem,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import PaletteOutlinedIcon from '@mui/icons-material/PaletteOutlined';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { LoadingState } from '../../components/common/LoadingState';
import { FormField, FormSection } from '../../components/ui/design-system';
import {
  fetchBrandingSettings,
  restoreBrandingDefaults,
  updateBrandingSettings,
} from '../../api/settings';
import { BRANDING_PRESETS } from '../../theme/brandingPresets';
import { createAppTheme } from '../../theme/createAppTheme';
import type { BrandingSettings, ThemePresetId } from '../../types/Settings';
import { useToast } from '../../context/ToastContext';
import { ThemeProvider } from '@mui/material/styles';

export default function BrandingPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['settings', 'branding'], queryFn: fetchBrandingSettings });
  const [form, setForm] = useState<BrandingSettings | null>(null);

  useEffect(() => {
    if (query.data) setForm(query.data);
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () => updateBrandingSettings(form ?? {}),
    onSuccess: async () => {
      showSuccess('Branding applied');
      await queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (error) => showError(String(error)),
  });

  const restoreMutation = useMutation({
    mutationFn: restoreBrandingDefaults,
    onSuccess: async (data) => {
      setForm(data);
      showSuccess('Default branding restored');
      await queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (error) => showError(String(error)),
  });

  const previewTheme = useMemo(() => {
    if (!form) return null;
    return createAppTheme({ mode: 'light', branding: form });
  }, [form]);

  const applyPreset = (presetId: ThemePresetId) => {
    const preset = BRANDING_PRESETS.find((item) => item.id === presetId);
    if (!preset || !form) return;
    setForm({
      ...form,
      theme_preset: presetId,
      ...preset.colors,
    });
  };

  if (query.isLoading || !form) return <LoadingState message="Loading branding settings…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Branding"
        subtitle="Configure company-wide colours, density, and visual style"
        action={
          <Stack direction="row" spacing={1}>
            <ProsohmButton
              buttonVariant="outlined"
              startIcon={<RestartAltIcon />}
              loading={restoreMutation.isPending}
              onClick={() => restoreMutation.mutate()}
            >
              Restore Defaults
            </ProsohmButton>
            <ProsohmButton
              startIcon={<PaletteOutlinedIcon />}
              loading={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              Apply Branding
            </ProsohmButton>
          </Stack>
        }
      />

      <Grid container spacing={2.5}>
        <Grid size={{ xs: 12, lg: 7 }}>
          <ContentCard title="Theme Presets">
            <Grid container spacing={1.5}>
              {BRANDING_PRESETS.map((preset) => (
                <Grid size={{ xs: 12, sm: 6 }} key={preset.id}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      cursor: 'pointer',
                      borderColor: form.theme_preset === preset.id ? 'primary.main' : 'divider',
                      borderWidth: form.theme_preset === preset.id ? 2 : 1,
                    }}
                    onClick={() => applyPreset(preset.id)}
                  >
                    <Typography sx={{ fontWeight: 700, mb: 0.5 }}>{preset.label}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {preset.description}
                    </Typography>
                    <Stack direction="row" spacing={0.75} sx={{ mt: 1.5 }}>
                      {Object.values(preset.colors)
                        .slice(0, 4)
                        .map((color) => (
                          <Box
                            key={color}
                            sx={{ width: 18, height: 18, borderRadius: 999, bgcolor: color }}
                          />
                        ))}
                    </Stack>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </ContentCard>

          <Box sx={{ mt: 2.5 }}>
            <ContentCard title="Custom Colours">
              <FormSection title="Palette">
                <Grid container spacing={2}>
                  {(
                    [
                      ['primary_color', 'Primary'],
                      ['secondary_color', 'Secondary'],
                      ['accent_color', 'Accent'],
                      ['success_color', 'Success'],
                      ['warning_color', 'Warning'],
                      ['danger_color', 'Danger'],
                      ['sidebar_color', 'Sidebar'],
                      ['header_color', 'Header'],
                    ] as const
                  ).map(([key, label]) => (
                    <Grid size={{ xs: 12, sm: 6, md: 4 }} key={key}>
                      <FormField
                        label={label}
                        value={form[key]}
                        onChange={(event) =>
                          setForm((current) =>
                            current ? { ...current, [key]: event.target.value } : current,
                          )
                        }
                      />
                    </Grid>
                  ))}
                </Grid>
              </FormSection>

              <FormSection title="Layout">
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <FormField
                      select
                      label="Button Style"
                      value={form.button_style}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? { ...current, button_style: event.target.value as BrandingSettings['button_style'] }
                            : current,
                        )
                      }
                    >
                      <MenuItem value="rounded">Rounded</MenuItem>
                      <MenuItem value="sharp">Sharp</MenuItem>
                      <MenuItem value="pill">Pill</MenuItem>
                    </FormField>
                  </Grid>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <FormField
                      select
                      label="Card Style"
                      value={form.card_style}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? { ...current, card_style: event.target.value as BrandingSettings['card_style'] }
                            : current,
                        )
                      }
                    >
                      <MenuItem value="elevated">Elevated</MenuItem>
                      <MenuItem value="flat">Flat</MenuItem>
                      <MenuItem value="bordered">Bordered</MenuItem>
                    </FormField>
                  </Grid>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <FormField
                      select
                      label="Application Density"
                      value={form.density}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? { ...current, density: event.target.value as BrandingSettings['density'] }
                            : current,
                        )
                      }
                    >
                      <MenuItem value="default">Default</MenuItem>
                      <MenuItem value="comfortable">Comfortable</MenuItem>
                      <MenuItem value="compact">Compact</MenuItem>
                    </FormField>
                  </Grid>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <FormField
                      type="number"
                      label="Border Radius"
                      value={form.border_radius}
                      onChange={(event) =>
                        setForm((current) =>
                          current
                            ? { ...current, border_radius: Number(event.target.value) }
                            : current,
                        )
                      }
                    />
                  </Grid>
                </Grid>
              </FormSection>
            </ContentCard>
          </Box>
        </Grid>

        <Grid size={{ xs: 12, lg: 5 }}>
          <ContentCard title="Live Preview">
            {previewTheme ? (
              <ThemeProvider theme={previewTheme}>
                <Paper sx={{ p: 2.5, borderRadius: 3 }}>
                  <Typography variant="sectionTitle" gutterBottom>
                    Preview Workspace
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                    <Chip label="Primary" sx={{ bgcolor: 'primary.main', color: 'primary.contrastText' }} />
                    <Chip label="Accent" sx={{ bgcolor: 'accent.main', color: 'accent.contrastText' }} />
                    <Chip label="Success" color="success" />
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <ProsohmButton buttonVariant="primary">Primary Action</ProsohmButton>
                    <ProsohmButton buttonVariant="outlined">Secondary</ProsohmButton>
                  </Stack>
                </Paper>
              </ThemeProvider>
            ) : null}
          </ContentCard>
        </Grid>
      </Grid>
    </PageContainer>
  );
}
