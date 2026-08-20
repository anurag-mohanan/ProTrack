import { useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Box,
  Chip,
  FormControlLabel,
  Grid,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { UnsavedChangesBar } from '../components/common/UnsavedChangesBar';
import { LoadingState } from '../components/common/LoadingState';
import { ContentCard } from '../components/ui/cards';
import { FormField, FormSection, StickyRecordHeader } from '../components/ui/design-system';
import { APP_TOP_BAR_OFFSET } from '../components/ui/design-system/StickyRecordHeader';
import { changePassword, fetchMyProfile, updateMyPreferences } from '../api/preferences';
import { fetchMyItProfile, itOperationsKeys } from '../api/itOperations';
import { ITProfilePanel } from '../components/it/ITProfilePanel';
import { useToast } from '../context/ToastContext';
import { formatCellValue, formatNumber } from '../utils/format';
import type { UserPreferences } from '../types/Preferences';
import { canAccessAdministration } from '../utils/permissions';

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
  const [searchParams] = useSearchParams();
  const tabFromQuery = searchParams.get('tab');
  const initialTab =
    tabFromQuery === 'preferences'
      ? 1
      : tabFromQuery === 'security' || tabFromQuery === 'password'
        ? 2
        : tabFromQuery === 'it'
          ? 3
          : 0;
  const [tab, setTab] = useState(initialTab);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [prefsForm, setPrefsForm] = useState<Partial<UserPreferences>>({});

  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);

  const profileQuery = useQuery({
    queryKey: ['auth', 'profile'],
    queryFn: fetchMyProfile,
  });

  const itProfileQuery = useQuery({
    queryKey: itOperationsKeys.profileMe(),
    queryFn: fetchMyItProfile,
    enabled: tab === 3,
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
      setPrefsForm({});
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
  const prefsDirty = Object.keys(prefsForm).length > 0;
  const passwordDirty = useMemo(
    () =>
      Boolean(
        passwordForm.current_password ||
          passwordForm.new_password ||
          passwordForm.confirm_password,
      ),
    [passwordForm],
  );
  const showUnsavedBar = (tab === 1 && prefsDirty) || (tab === 2 && passwordDirty);

  return (
    <PageContainer>
      <PageHeader
        title="My Profile"
        subtitle="Account details, appearance preferences, and activity summary"
      />

      <StickyRecordHeader
        compact
        primaryLabel={`${profile.first_name} ${profile.last_name}`.trim()}
        secondaryLabel={profile.email}
        stickyTop={APP_TOP_BAR_OFFSET}
        meta={
          <>
            {profile.role_name ? <Chip size="small" label={profile.role_name} /> : null}
            {profile.team_name ? <Chip size="small" variant="outlined" label={profile.team_name} /> : null}
          </>
        }
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
              <Tab label="Profile" />
              <Tab label="Preferences" />
              <Tab label="Password" />
              <Tab label="IT" />
            </Tabs>

            <Box sx={{ p: 3 }}>
              {tab === 0 ? (
                <FormSection title="Profile Details">
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Department" value={formatCellValue(profile.department_name)} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Team" value={formatCellValue(profile.team_name)} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Manager" value={formatCellValue(profile.manager_name)} slotProps={{ input: { readOnly: true } }} />
                    </Grid>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <FormField label="Phone" value={formatCellValue(profile.phone)} slotProps={{ input: { readOnly: true } }} />
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
                <>
                <FormSection title="Theme & Appearance">
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
                        {canAccessAdministration(profile.role_name) ? (
                          <MenuItem value="admin">Administrator Workspace</MenuItem>
                        ) : null}
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
                </FormSection>

                <FormSection title="Notification Preferences">
                  <FormControlLabel
                    control={
                      <Switch
                        checked={preferences.email_notifications_enabled ?? true}
                        onChange={(event) =>
                          setPrefsForm((current) => ({
                            ...current,
                            email_notifications_enabled: event.target.checked,
                          }))
                        }
                      />
                    }
                    label="Receive email notifications"
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    System notification categories are managed in the Administrator Workspace.
                  </Typography>
                </FormSection>

                </>
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
                </FormSection>
              ) : null}

              {tab === 3 ? (
                <FormSection title="My IT Profile">
                  <ITProfilePanel
                    profile={itProfileQuery.data}
                    loading={itProfileQuery.isLoading}
                    emptyMessage="You have no assigned IT assets, accounts, or IP allocations."
                  />
                </FormSection>
              ) : null}
            </Box>
          </ContentCard>
        </Grid>
      </Grid>

      <UnsavedChangesBar
        visible={showUnsavedBar}
        saveLabel={tab === 2 ? 'Update Password' : 'Save Preferences'}
        onSave={() => {
          if (tab === 2) {
            if (passwordForm.new_password !== passwordForm.confirm_password) {
              showError('Passwords do not match');
              return;
            }
            passwordMutation.mutate({
              current_password: passwordForm.current_password,
              new_password: passwordForm.new_password,
              confirm_password: passwordForm.confirm_password,
            });
            return;
          }
          preferencesMutation.mutate(preferences);
        }}
        onDiscard={() => {
          if (tab === 2) {
            setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
            return;
          }
          setPrefsForm({});
        }}
        saving={preferencesMutation.isPending || passwordMutation.isPending}
      />
    </PageContainer>
  );
}
