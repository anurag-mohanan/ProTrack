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
import DriveFileMoveIcon from '@mui/icons-material/DriveFileMove';
import GroupsIcon from '@mui/icons-material/Groups';
import type { GridColDef } from '@mui/x-data-grid';
import { apiClient } from '../../api/client';
import { fetchUsers } from '../../api/lookups';
import { teamsApi } from '../../api/resources';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { LoadingState } from '../../components/common/LoadingState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageContainer } from '../../components/common/PageContainer';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { AdminDeleteButton } from '../../components/admin/AdminDeleteButton';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  DrawerQuickActions,
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
  RecordDetailDrawer,
  SearchToolbar,
  TableRowActions,
} from '../../components/ui/design-system';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { DATA_GRID_ACTIONS_COLUMN_WIDTH } from '../../theme/componentStyles';
import { useOpenCreateFromQuery } from '../../hooks/useOpenCreateFromQuery';
import type { Team, TeamCreate, TeamMember, TeamMemberCreate, TeamMemberTransfer } from '../../types/Team';
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
  business_unit: string;
}

const emptyForm: TeamFormState = {
  name: '',
  description: '',
  team_lead_id: '',
  colour: '#1976d2',
  is_active: true,
  business_unit: '',
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
    is_billable_headcount: true,
  });
  const [removeMemberTarget, setRemoveMemberTarget] = useState<TeamMember | null>(null);
  const [moveMemberTarget, setMoveMemberTarget] = useState<TeamMember | null>(null);
  const [moveForm, setMoveForm] = useState<TeamMemberTransfer>({
    target_team_id: '',
    effective_from: new Date().toISOString().slice(0, 10),
  });
  const [moving, setMoving] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [teamsData, usersData] = await Promise.all([
        teamsApi.list({ limit: 500 }),
        fetchUsers(),
      ]);
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
      business_unit: team.business_unit ?? '',
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
        business_unit: optionalString(form.business_unit),
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

  const FIXED_RESOURCE_ROLES = new Set([
    'Senior Designer',
    'Designer',
    'Junior Designer',
    'Surfacer',
  ]);

  const defaultBillableForUser = (team: Team, userId: string) => {
    if (
      team.name === 'Corporate / Management' ||
      team.name === 'Corporate / Shared Services' ||
      team.name === 'Management'
    ) {
      return false;
    }
    const selected = users.find((u) => u.id === userId);
    const role = selected?.role_name ?? '';
    return FIXED_RESOURCE_ROLES.has(role);
  };

  const openMembers = async (team: Team) => {
    setMemberTeam(team);
    setMemberForm({
      user_id: '',
      role_within_team: '',
      is_billable_headcount: false,
    });
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
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    }
  };

  const handleToggleBillable = async (member: TeamMember, next: boolean) => {
    if (!memberTeam) return;
    try {
      await apiClient.patch(`/teams/${memberTeam.id}/members/${member.id}`, {
        is_billable_headcount: next,
      });
      showSuccess(next ? 'Marked billable for retainer headcount' : 'Excluded from retainer headcount');
      await openMembers(memberTeam);
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

  const transferableTeams = useMemo(() => {
    if (!memberTeam) return [];
    return teams.filter((team) => team.is_active && team.id !== memberTeam.id);
  }, [memberTeam, teams]);

  const openMoveMember = (member: TeamMember) => {
    setMoveMemberTarget(member);
    setMoveForm({
      target_team_id: '',
      effective_from: new Date().toISOString().slice(0, 10),
    });
  };

  const handleMoveMember = async () => {
    if (!memberTeam || !moveMemberTarget) return;
    if (!moveForm.target_team_id) {
      showError('Select a target team');
      return;
    }
    setMoving(true);
    try {
      await teamsApi.transferMember(memberTeam.id, moveMemberTarget.id, {
        target_team_id: moveForm.target_team_id,
        effective_from: moveForm.effective_from || undefined,
      });
      const targetName =
        teams.find((team) => team.id === moveForm.target_team_id)?.name ?? 'target team';
      showSuccess(
        `${moveMemberTarget.user_name} → ${targetName} from ${moveForm.effective_from}. Salary is prorated by calendar days in each month.`,
      );
      setMoveMemberTarget(null);
      await openMembers(memberTeam);
      await loadData();
    } catch (error) {
      showError(getErrorMessage(error));
    } finally {
      setMoving(false);
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
    { field: 'business_unit', headerName: 'Business unit', flex: 0.8, minWidth: 120, valueFormatter: (value) => formatCellValue(value as string | null) },
    { field: 'team_lead_name', headerName: 'Team Lead', flex: 1, minWidth: 140 },
    {
      field: 'billable_member_count',
      headerName: 'Billable / Members',
      width: 150,
      valueGetter: (_value, row) =>
        `${row.billable_member_count ?? 0} / ${row.member_count ?? 0}`,
      renderCell: (params) => (
        <Box title="Billable = designers/surfacer for customer fixed/retainer cost. Others are Prosohm overhead.">
          <strong>{params.row.billable_member_count ?? 0}</strong>
          <Box component="span" sx={{ color: 'text.secondary' }}>
            {' '}
            / {params.row.member_count ?? 0}
          </Box>
        </Box>
      ),
    },
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
        subtitle="Delivery engineers count toward customer fixed/retainer cost; managers and HQ are Prosohm overhead"
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
        <ClientPaginatedDataGrid
          rows={filteredTeams}
          columns={columns}
          autoHeight
          filterKey={search}
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
              <FormField
                label="Business unit"
                value={form.business_unit}
                onChange={(event) => setForm({ ...form, business_unit: event.target.value })}
                helper="Portfolio dimension for filters (e.g. Engineering, Corporate)"
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
                onChange={(event) => {
                  const userId = String(event.target.value);
                  setMemberForm({
                    ...memberForm,
                    user_id: userId,
                    is_billable_headcount: memberTeam
                      ? defaultBillableForUser(memberTeam, userId)
                      : false,
                  });
                }}
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
            <Grid size={{ xs: 12 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={Boolean(memberForm.is_billable_headcount)}
                    onChange={(event) =>
                      setMemberForm({
                        ...memberForm,
                        is_billable_headcount: event.target.checked,
                      })
                    }
                  />
                }
                label="Billable headcount (customer fixed / retainer cost)"
              />
              <Box sx={{ color: 'text.secondary', fontSize: '0.875rem', mt: 0.5 }}>
                On only for delivery engineers (Senior Designer, Designer, Junior Designer, Surfacer).
                Office Admin, Planning Board, Design Leader, Engineering Manager and similar roles are
                Prosohm overhead — paid by the company, not customers. Corporate defaults off.
              </Box>
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
                    gap: 1,
                    flexWrap: 'wrap',
                  }}
                >
                  <Box sx={{ minWidth: 180 }}>
                    <Box sx={{ fontWeight: 600 }}>{member.user_name}</Box>
                    <Box sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                      {member.role_within_team || 'Member'} · {member.user_email}
                      {member.effective_from
                        ? ` · from ${member.effective_from}`
                        : ''}
                      {member.is_primary ? ' · Primary home' : ''}
                    </Box>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {member.is_primary ? (
                      <IconButton
                        size="small"
                        color="primary"
                        aria-label={`Move ${member.user_name} to another team`}
                        title="Move to another team (effective date)"
                        onClick={() => openMoveMember(member)}
                      >
                        <DriveFileMoveIcon fontSize="small" />
                      </IconButton>
                    ) : null}
                    <FormControlLabel
                      control={
                        <Switch
                          size="small"
                          checked={member.is_billable_headcount !== false}
                          onChange={(event) =>
                            void handleToggleBillable(member, event.target.checked)
                          }
                        />
                      }
                      label="Billable"
                    />
                    <IconButton
                      size="small"
                      color="error"
                      aria-label={`Remove ${member.user_name}`}
                      onClick={() => setRemoveMemberTarget(member)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
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
              label="Billable / Members"
              value={`${selectedTeam.billable_member_count ?? 0} / ${selectedTeam.member_count ?? 0}`}
              slotProps={{ input: { readOnly: true } }}
            />
          </FormSection>
        ) : null}
      </RecordDetailDrawer>

      <FormDrawer
        open={Boolean(moveMemberTarget)}
        onClose={() => setMoveMemberTarget(null)}
        title="Move resource"
        subtitle={moveMemberTarget ? `${moveMemberTarget.user_name} · ${memberTeam?.name}` : undefined}
        icon={DriveFileMoveIcon}
        formId="move-member-form"
        submitLabel="Move"
        loading={moving}
      >
        <Box
          component="form"
          id="move-member-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleMoveMember();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}
        >
          <FormSection title="Transfer details" icon={DriveFileMoveIcon}>
            <Grid size={{ xs: 12 }}>
              <Box sx={{ color: 'text.secondary', fontSize: '0.875rem', mb: 1 }}>
                The resource is counted on the current team up to the day before the effective
                date, then on the target team. July example: effective 20 Jul → 19 days on source,
                12 days on target.
              </Box>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <FormSelect
                label="Target team"
                searchable
                required
                value={moveForm.target_team_id}
                options={transferableTeams.map((team) => ({
                  value: team.id,
                  label: team.name,
                }))}
                onChange={(event) =>
                  setMoveForm({ ...moveForm, target_team_id: String(event.target.value) })
                }
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <FormField
                label="Effective from"
                type="date"
                required
                value={moveForm.effective_from ?? ''}
                onChange={(event) =>
                  setMoveForm({ ...moveForm, effective_from: event.target.value })
                }
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Grid>
          </FormSection>
        </Box>
      </FormDrawer>

      <ConfirmDialog
        open={Boolean(removeMemberTarget)}
        title="Remove Team Member"
        recordName={removeMemberTarget?.user_name ?? undefined}
        message="This member will be removed from the team. They will not be deleted from ProTrack."
        confirmLabel="Remove"
        danger
        onClose={() => setRemoveMemberTarget(null)}
        onConfirm={() => {
          if (removeMemberTarget) {
            void handleRemoveMember(removeMemberTarget.id);
            setRemoveMemberTarget(null);
          }
        }}
      />
    </PageContainer>
  );
}
