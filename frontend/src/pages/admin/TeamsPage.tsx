import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Grid,
  IconButton,
  Switch,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import GroupsIcon from '@mui/icons-material/Groups';
import type { GridColDef } from '@mui/x-data-grid';
import { apiClient } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import { teamsApi } from '../../api/resources';
import { LoadingState } from '../../components/common/LoadingState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  ProsohmDataGrid,
  RecordDetailDrawer,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import type { Team, TeamCreate, TeamMember, TeamMemberCreate } from '../../types/Team';
import { getErrorMessage } from '../../api/client';
import { formatCellValue, userDisplayName } from '../../utils/format';
import { optionalString, optionalUuid, validateRequiredFields } from '../../utils/formValues';
import { canDeleteRecords } from '../../utils/permissions';
import type { User } from '../../types';

interface TeamFormState {
  name: string;
  description: string;
  team_lead_id: string;
  colour: string;
  is_active: boolean;
}

const emptyForm: TeamFormState = {
  name: '',
  description: '',
  team_lead_id: '',
  colour: '#1976d2',
  is_active: true,
};

export default function TeamsPage() {
  const { user } = useAuth();
  const isAdmin = canDeleteRecords(user?.role_name ?? '');
  const { showSuccess, showError } = useToast();
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [form, setForm] = useState<TeamFormState>(emptyForm);
  const [memberTeam, setMemberTeam] = useState<Team | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [memberForm, setMemberForm] = useState<TeamMemberCreate>({
    user_id: '',
    role_within_team: '',
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [teamsData, usersData] = await Promise.all([teamsApi.list(), fetchUsers()]);
      setTeams(teamsData);
      setUsers(usersData);
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredTeams = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return teams;
    return teams.filter((team) =>
      [team.name, team.description ?? ''].join(' ').toLowerCase().includes(term),
    );
  }, [search, teams]);

  const openCreate = () => {
    setEditingTeam(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  useOpenCreateFromQuery(openCreate);

  const openEdit = (team: Team) => {
    setEditingTeam(team);
    setForm({
      name: team.name,
      description: team.description ?? '',
      team_lead_id: team.team_lead_id ?? '',
      colour: team.colour,
      is_active: team.is_active,
    });
    setFormOpen(true);
  };

  const handleSave = async () => {
    const validationError = validateRequiredFields(form, [{ key: 'name', label: 'Team name' }]);
    if (validationError) {
      showError(validationError);
      return;
    }
    setSaving(true);
    try {
      const payload: TeamCreate = {
        name: form.name.trim(),
        description: optionalString(form.description),
        team_lead_id: optionalUuid(form.team_lead_id),
        colour: form.colour,
        is_active: form.is_active,
      };
      if (editingTeam) {
        await teamsApi.update(editingTeam.id, payload);
        showSuccess('Team updated');
      } else {
        await teamsApi.create(payload);
        showSuccess('Team created');
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  const openMembers = async (team: Team) => {
    setMemberTeam(team);
    try {
      const { data } = await apiClient.get<TeamMember[]>(`/teams/${team.id}/members`);
      setMembers(data);
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const handleAddMember = async () => {
    if (!memberTeam || !memberForm.user_id) return;
    try {
      await apiClient.post(`/teams/${memberTeam.id}/members`, memberForm);
      showSuccess('Member added');
      await openMembers(memberTeam);
      setMemberForm({ user_id: '', role_within_team: '' });
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    if (!memberTeam) return;
    try {
      await apiClient.delete(`/teams/${memberTeam.id}/members/${memberId}`);
      showSuccess('Member removed');
      await openMembers(memberTeam);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const columns: GridColDef<Team>[] = [
    {
      field: 'name',
      headerName: 'Team Name',
      flex: 1.2,
      minWidth: 160,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: params.row.colour,
            }}
          />
          {params.value}
        </Box>
      ),
    },
    { field: 'description', headerName: 'Description', flex: 1.5, minWidth: 180, valueFormatter: (value) => formatCellValue(value as string | null) },
    { field: 'team_lead_name', headerName: 'Team Lead', flex: 1, minWidth: 140 },
    { field: 'member_count', headerName: 'Members', width: 100 },
    {
      field: 'is_active',
      headerName: 'Active',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ),
    },
    {
      field: 'actions',
      headerName: '',
      width: isAdmin ? DATA_GRID_ACTIONS_COLUMN_WIDTH + 40 : DATA_GRID_ACTIONS_COLUMN_WIDTH,
      sortable: false,
      filterable: false,
      renderCell: (params) => (
        <TableRowActions
          onEdit={() => openEdit(params.row)}
          deleteAction={
            isAdmin ? (
              <AdminDeleteButton
                resource="teams"
                recordId={params.row.id}
                recordName={params.row.name}
                onDeleted={() => void loadData()}
                onDeactivate={async () => {
                  await teamsApi.update(params.row.id, { is_active: false });
                  showSuccess('Team deactivated.');
                  await loadData();
                }}
              />
            ) : undefined
          }
        />
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading teams…" />;

  return (
    <PageContainer>
      <PageHeader
        title="Teams"
        subtitle="Manage engineering teams, leads, and membership"
        action={
          <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
            Create Team
          </ProsohmButton>
        }
      />

      <SearchToolbar>
        <FormField
          label="Search teams"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 280, flex: 1 }}
        />
      </SearchToolbar>

      <ContentCard noPadding>
        <ProsohmDataGrid
          rows={filteredTeams}
          columns={columns}
          autoHeight
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { pageSize: 10 } },
          }}
          onRowOpen={(rowId) => {
            const team = filteredTeams.find((item) => item.id === rowId);
            if (team) setSelectedTeam(team);
          }}
        />
      </ContentCard>

      <FormDrawer
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingTeam ? 'Edit Team' : 'Create Team'}
        subtitle="Configure team profile, lead, and status."
        icon={GroupsIcon}
        formId="team-form"
        submitLabel={editingTeam ? 'Save Changes' : 'Create Team'}
        loading={saving}
      >
        <Box
          component="form"
          id="team-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSave();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Team Profile" icon={GroupsIcon}>
            <Grid size={{ xs: 12, sm: 8 }}>
              <FormField
                label="Team Name"
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <FormField
                label="Colour"
                type="color"
                value={form.colour}
                onChange={(event) => setForm({ ...form, colour: event.target.value })}
              />
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormField
                label="Description"
                multiline
                rows={3}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="Team Lead"
                searchable
                value={form.team_lead_id}
                options={[
                  { value: '', label: 'None' },
                  ...users.map((user) => ({
                    value: user.id,
                    label: userDisplayName(user),
                  })),
                ]}
                onChange={(event) =>
                  setForm({ ...form, team_lead_id: String(event.target.value) })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm({ ...form, is_active: event.target.checked })
                    }
                  />
                }
                label="Active"
              />
            </Grid>
          </FormSection>
        </Box>
      </FormDrawer>

      <FormDrawer
        open={Boolean(memberTeam)}
        onClose={() => setMemberTeam(null)}
        title="Team Members"
        subtitle={memberTeam?.name}
        icon={GroupsIcon}
        formId="member-form"
        submitLabel="Add Member"
      >
        <Box
          component="form"
          id="member-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleAddMember();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Add Member" icon={GroupsIcon}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormSelect
                label="User"
                searchable
                required
                value={memberForm.user_id}
                options={users.map((user) => ({
                  value: user.id,
                  label: userDisplayName(user),
                }))}
                onChange={(event) =>
                  setMemberForm({ ...memberForm, user_id: String(event.target.value) })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Role within Team"
                value={memberForm.role_within_team ?? ''}
                onChange={(event) =>
                  setMemberForm({ ...memberForm, role_within_team: event.target.value })
                }
              />
            </Grid>
          </FormSection>
          <FormSection title="Current Members" icon={GroupsIcon}>
            {members.map((member) => (
              <Grid size={{ xs: 12 }} key={member.id}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    py: 1,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Box>
                    <Box sx={{ fontWeight: 600 }}>{member.user_name}</Box>
                    <Box sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                      {member.role_within_team || 'Member'} · {member.user_email}
                    </Box>
                  </Box>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => void handleRemoveMember(member.id)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
              </Grid>
            ))}
          </FormSection>
        </Box>
      </FormDrawer>

      <RecordDetailDrawer
        open={Boolean(selectedTeam)}
        onClose={() => setSelectedTeam(null)}
        title={selectedTeam?.name ?? 'Team'}
        subtitle="Engineering team"
        icon={GroupsIcon}
        status={
          selectedTeam ? (
            <Chip
              label={selectedTeam.is_active ? 'Active' : 'Inactive'}
              size="small"
              color={selectedTeam.is_active ? 'success' : 'default'}
            />
          ) : null
        }
        quickActions={
          selectedTeam ? (
            <DrawerQuickActions>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  openEdit(selectedTeam);
                  setSelectedTeam(null);
                }}
              >
                Edit
              </ProsohmButton>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  void openMembers(selectedTeam);
                  setSelectedTeam(null);
                }}
              >
                Manage Members
              </ProsohmButton>
              {isAdmin ? (
                <AdminDeleteButton
                  mode="button"
                  resource="teams"
                  recordId={selectedTeam.id}
                  recordName={selectedTeam.name}
                  onDeleted={() => {
                    setSelectedTeam(null);
                    void loadData();
                  }}
                  onDeactivate={async () => {
                    await teamsApi.update(selectedTeam.id, { is_active: false });
                    showSuccess('Team deactivated.');
                    setSelectedTeam(null);
                    await loadData();
                  }}
                />
              ) : null}
            </DrawerQuickActions>
          ) : null
        }
      >
        {selectedTeam ? (
          <FormSection title="Overview" icon={GroupsIcon}>
            <FormField label="Team Name" value={selectedTeam.name} slotProps={{ input: { readOnly: true } }} />
            <FormField
              label="Description"
              value={formatCellValue(selectedTeam.description) || '—'}
              multiline
              minRows={2}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Team Lead"
              value={formatCellValue(selectedTeam.team_lead_name) || '—'}
              slotProps={{ input: { readOnly: true } }}
            />
            <FormField
              label="Members"
              value={String(selectedTeam.member_count ?? 0)}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>
    </PageContainer>
  );
}
