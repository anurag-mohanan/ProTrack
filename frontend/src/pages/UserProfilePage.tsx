import { useState } from 'react';
import {
  Avatar,
  Box,
  Chip,
  Grid,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { LoadingState } from '../components/common/LoadingState';
import { ContentCard } from '../components/ui/cards';
import { FormField, FormSection } from '../components/ui/design-system';
import { ProsohmButton } from '../components/ui/ProsohmButton';
import {
  changePassword,
  fetchMyProfile,
  updateMyPreferences,
} from '../api/preferences';
import { useToast } from '../context/ToastContext';
import { formatNumber } from '../utils/format';
import type { UserPreferences } from '../types/Preferences';

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <ContentCard>
      <Typography variant="captionLabel" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="sectionTitle">{value}</Typography>
    </ContentCard>
  );
}

export default function UserProfilePage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [prefsForm, setPrefsForm] = useState<Partial<UserPreferences>>({});

  const profileQuery = useQuery({
    queryKey: ['auth', 'profile'],
    queryFn: fetchMyProfile,
  });

  const passwordMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      showSuccess('Password updated');
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    },
    onError: (error) => showError(String(error)),
  });

  const preferencesMutation = useMutation({
    mutationFn: updateMyPreferences,
    onSuccess: async () => {
      showSuccess('Preferences saved');
      await queryClient.invalidateQueries({ queryKey: ['preferences', 'me'] });
      await queryClient.invalidateQueries({ queryKey: ['auth', 'profile'] });
      await queryClient.invalidateQueries({ queryKey: ['settings', 'public'] });
    },
    onError: (error) => showError(String(error)),
  });

  if (profileQuery.isLoading || !profileQuery.data) {
    return <LoadingState message="Loading profile…" />;
  }

  const profile = profileQuery.data;
  const preferences = { ...profile.preferences, ...prefsForm };
  const initials = `${profile.first_name[0] ?? ''}${profile.last_name[0] ?? ''}`.toUpperCase();

  return (
    <PageContainer>
      <PageHeader
        title="My Profile"
        subtitle="Account details, appearance preferences, and activity summary"
      />

      <Grid container spacing={2.5}>
        <Grid size={{ xs: 12, md: 4 }}>
          <ContentCard>
            <Stack spacing={2} sx={{ py: 1, alignItems: 'center' }}>
              <Avatar sx={{ width: 88, height: 88, bgcolor: 'primary.main', fontSize: '1.75rem' }}>
                {initials}
              </Avatar>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="sectionTitle">
                  {profile.first_name} {profile.last_name}
                </Typography>
                <Typography color="text.secondary">{profile.designation || profile.role_name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {profile.email}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', justifyContent: 'center' }}>
                {profile.department_name ? <Chip size="small" label={profile.department_name} /> : null}
                {profile.team_name ? <Chip size="small" label={profile.team_name} /> : null}
              </Stack>
            </Stack>
          </ContentCard>

          <Box sx={{ mt: 2.5 }}>
            <Grid container spacing={1.5}>
              <Grid size={{ xs: 6 }}>
                <MetricTile label="Active Projects" value={String(profile.summary.active_projects)} />
              </Grid>
              <Grid size={{ xs: 6 }}>
                <MetricTile
                  label="Utilization"
                  value={`${formatNumber(Number(profile.summary.utilization_percent))}%`}
                />
              </Grid>
              <Grid size={{ xs: 6 }}>
                <MetricTile
                  label="Quoted Hours"
                  value={formatNumber(Number(profile.summary.quoted_hours_assigned))}
                />
              </Grid>
              <Grid size={{ xs: 6 }}>
                <MetricTile label="Timesheets" value={String(profile.summary.timesheet_count)} />
              </Grid>
            </Grid>
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 8 }}>
          <ContentCard noPadding>
            <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}>
              <Tab label="Overview" />
              <Tab label="Preferences" />
              <Tab label="Security" />
            </Tabs>

            <Box sx={{ p: 3 }}>
              {tab === 0 ? (
                <FormSection title="Profile Details">
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Department" value={profile.department_name ?? '—'} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Team" value={profile.team_name ?? '—'} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Manager" value={profile.manager_name ?? '—'} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Phone" value={profile.phone ?? '—'} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12 }}>
                      <Typography variant="captionLabel" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                        Skills
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }} useFlexGap>
                        {profile.skills.length ? (
                          profile.skills.map((skill) => (
                            <Chip
                              key={skill.skill_id}
                              label={`${skill.skill_name ?? 'Skill'} · ${skill.proficiency}`}
                              size="small"
                            />
                          ))
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            No skills recorded yet.
                          </Typography>
                        )}
                      </Stack>
                    </Grid>
                  </Grid>
                </FormSection>
              ) : null}

              {tab === 1 ? (
                <FormSection title="Appearance & Workspace">
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        select
                        label="Theme"
                        value={preferences.theme_mode}
                        onChange={(event) =>
                          setPrefsForm((current) => ({
                            ...current,
                            theme_mode: event.target.value as UserPreferences['theme_mode'],
                          }))
                        }
                      >
                        <MenuItem value="company_default">Follow Company Default</MenuItem>
                        <MenuItem value="system">Follow Windows Theme</MenuItem>
                        <MenuItem value="light">Light Mode</MenuItem>
                        <MenuItem value="dark">Dark Mode</MenuItem>
                      </FormField>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        select
                        label="Default Landing Page"
                        value={preferences.default_landing_page}
                        onChange={(event) =>
                          setPrefsForm((current) => ({
                            ...current,
                            default_landing_page: event.target.value as UserPreferences['default_landing_page'],
                          }))
                        }
                      >
                        <MenuItem value="dashboard">Dashboard</MenuItem>
                        <MenuItem value="projects">Projects</MenuItem>
                        <MenuItem value="timesheets">Timesheets</MenuItem>
                      </FormField>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        select
                        label="Dashboard Layout"
                        value={preferences.dashboard_layout}
                        onChange={(event) =>
                          setPrefsForm((current) => ({
                            ...current,
                            dashboard_layout: event.target.value as UserPreferences['dashboard_layout'],
                          }))
                        }
                      >
                        <MenuItem value="default">Default</MenuItem>
                        <MenuItem value="comfortable">Comfortable</MenuItem>
                        <MenuItem value="compact">Compact</MenuItem>
                      </FormField>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        select
                        label="Table Density"
                        value={preferences.table_density}
                        onChange={(event) =>
                          setPrefsForm((current) => ({
                            ...current,
                            table_density: event.target.value as UserPreferences['table_density'],
                          }))
                        }
                      >
                        <MenuItem value="comfortable">Comfortable</MenuItem>
                        <MenuItem value="compact">Compact</MenuItem>
                      </FormField>
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        select
                        label="Font Size"
                        value={preferences.font_size}
                        onChange={(event) =>
                          setPrefsForm((current) => ({
                            ...current,
                            font_size: event.target.value as UserPreferences['font_size'],
                          }))
                        }
                      >
                        <MenuItem value="small">Small</MenuItem>
                        <MenuItem value="medium">Medium</MenuItem>
                        <MenuItem value="large">Large</MenuItem>
                      </FormField>
                    </Grid>
                  </Grid>
                  <Box sx={{ mt: 3 }}>
                    <ProsohmButton
                      loading={preferencesMutation.isPending}
                      onClick={() => preferencesMutation.mutate(preferences)}
                    >
                      Save Preferences
                    </ProsohmButton>
                  </Box>
                </FormSection>
              ) : null}

              {tab === 2 ? (
                <FormSection title="Change Password">
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12 }}>
                      <FormField
                        label="Current Password"
                        type="password"
                        value={passwordForm.current_password}
                        onChange={(event) =>
                          setPasswordForm((current) => ({
                            ...current,
                            current_password: event.target.value,
                          }))
                        }
                      />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        label="New Password"
                        type="password"
                        value={passwordForm.new_password}
                        onChange={(event) =>
                          setPasswordForm((current) => ({
                            ...current,
                            new_password: event.target.value,
                          }))
                        }
                      />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField
                        label="Confirm Password"
                        type="password"
                        value={passwordForm.confirm_password}
                        onChange={(event) =>
                          setPasswordForm((current) => ({
                            ...current,
                            confirm_password: event.target.value,
                          }))
                        }
                      />
                    </Grid>
                  </Grid>
                  <Box sx={{ mt: 3 }}>
                    <ProsohmButton
                      loading={passwordMutation.isPending}
                      onClick={() => {
                        if (passwordForm.new_password !== passwordForm.confirm_password) {
                          showError('Passwords do not match');
                          return;
                        }
                        passwordMutation.mutate({
                          current_password: passwordForm.current_password,
                          new_password: passwordForm.new_password,
                        });
                      }}
                    >
                      Update Password
                    </ProsohmButton>
                  </Box>
                </FormSection>
              ) : null}
            </Box>
          </ContentCard>
        </Grid>
      </Grid>
    </PageContainer>
  );
}
