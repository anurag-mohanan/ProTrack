import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  FormControlLabel,
  Grid,
  IconButton,
  Switch,
  Tooltip,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import GroupsIcon from '@mui/icons-material/Groups';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { apiClient } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import { teamsApi } from '../../api/resources';
import { LoadingState } from '../../components/common/LoadingState';
import { PageHeader } from '../../components/common/PageHeader';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  SearchToolbar,
  DeleteDialog,
  EmptyState,
} from '../../components/ui/design-system';
import { useToast } from '../../context/ToastContext';
import { prosohmDataGridSx } from '../../theme/componentStyles';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import type { Team, TeamCreate, TeamMember, TeamMemberCreate } from '../../types/Team';
import { getErrorMessage } from '../../api/client';
import { userDisplayName } from '../../utils/format';
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
  const theme = useTheme();
  const gridSx = useMemo(() => prosohmDataGridSx(theme), [theme]);
  const { showSuccess, showError } = useToast();
  const [teams, setTeams] = useState<Team[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [form, setForm] = useState<TeamFormState>(emptyForm);
  const [deleteTarget, setDeleteTarget] = useState<Team | null>(null);
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
    if (!form.name.trim()) {
      showError('Team name is required.');
      return;
    }
    setSaving(true);
    try {
      const payload: TeamCreate = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        team_lead_id: form.team_lead_id || null,
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

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await teamsApi.remove(deleteTarget.id);
      showSuccess('Team deleted');
      setDeleteTarget(null);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
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
    { field: 'description', headerName: 'Description', flex: 1.5, minWidth: 180 },
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
      headerName: 'Actions',
      width: 130,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title="Manage members">
            <IconButton size="small" onClick={() => void openMembers(params.row)}>
              <GroupsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <IconButton size="small" onClick={() => openEdit(params.row)}>
            <EditIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" color="error" onClick={() => setDeleteTarget(params.row)}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  if (loading) return <LoadingState message="Loading teams…" />;

  return (
    <Box>
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
        {filteredTeams.length === 0 ? (
          <EmptyState
            title="No teams found"
            description="Create a team to organize designers and projects."
            action={
              <ProsohmButton buttonVariant="primary" startIcon={<AddIcon />} onClick={openCreate}>
                Create Team
              </ProsohmButton>
            }
          />
        ) : (
          <DataGrid rows={filteredTeams} columns={columns} autoHeight sx={gridSx} />
        )}
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

      <DeleteDialog
        open={Boolean(deleteTarget)}
        objectLabel="Team"
        objectName={deleteTarget?.name ?? ''}
        extraMessage="Projects linked to this team will have their team cleared."
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDelete()}
      />
    </Box>
  );
}
