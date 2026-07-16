import { useCallback, useMemo, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/common/PageHeader';
import { teamsApi } from '../api/resources';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { isAdminRole } from '../utils/permissions';
import type { OrgChartPerson, OrgChartTeamColumn } from '../types/Team';

const ORG_CHART_KEY = ['teams', 'organization-chart'] as const;

type PendingMove = {
  person: OrgChartPerson;
  targetTeam: OrgChartTeamColumn;
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function PersonCard({
  person,
  accent,
  canEdit,
  onDragStart,
}: {
  person: OrgChartPerson;
  accent: string;
  canEdit: boolean;
  onDragStart: (person: OrgChartPerson) => void;
}) {
  const draggable = canEdit && person.can_move;

  return (
    <Box
      draggable={draggable}
      onDragStart={(event) => {
        if (!draggable) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.setData('application/x-protrack-user', person.user_id);
        event.dataTransfer.effectAllowed = 'move';
        onDragStart(person);
      }}
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        cursor: draggable ? 'grab' : 'default',
        transition: 'box-shadow 0.15s ease, transform 0.15s ease',
        '&:active': draggable ? { cursor: 'grabbing' } : undefined,
        '&:hover': draggable
          ? {
              boxShadow: 3,
              transform: 'translateY(-1px)',
            }
          : undefined,
        position: 'relative',
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 4,
          bgcolor: accent,
        },
      }}
    >
      <Stack direction="row" spacing={1.25} sx={{ alignItems: 'flex-start' }}>
        {draggable ? (
          <DragIndicatorIcon sx={{ mt: 0.5, color: 'text.disabled', fontSize: 18 }} />
        ) : (
          <Box sx={{ width: 18 }} />
        )}
        <Avatar
          sx={{
            width: 36,
            height: 36,
            fontSize: 13,
            fontWeight: 700,
            bgcolor: accent,
          }}
        >
          {initials(person.name)}
        </Avatar>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.25 }} noWrap>
            {person.name}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
            {person.designation || person.role_name || 'Team member'}
          </Typography>
          <Stack direction="row" spacing={0.5} useFlexGap sx={{ mt: 0.75, flexWrap: 'wrap' }}>
            {person.stream_name ? (
              <Chip label={person.stream_name} size="small" variant="outlined" sx={{ height: 22 }} />
            ) : null}
            {person.is_billable_headcount ? (
              <Chip label="Billable" size="small" color="success" variant="outlined" sx={{ height: 22 }} />
            ) : null}
            {!person.is_primary && person.member_id == null ? (
              <Chip label="Unassigned" size="small" color="warning" sx={{ height: 22 }} />
            ) : null}
          </Stack>
          {person.manager_name ? (
            <Typography
              variant="caption"
              color="text.secondary"
              noWrap
              sx={{ mt: 0.5, display: 'block' }}
            >
              Reports to {person.manager_name}
            </Typography>
          ) : null}
        </Box>
      </Stack>
    </Box>
  );
}

function TeamColumn({
  team,
  canEdit,
  dropTargetId,
  setDropTargetId,
  onPersonDragStart,
  onDropPerson,
}: {
  team: OrgChartTeamColumn;
  canEdit: boolean;
  dropTargetId: string | null;
  setDropTargetId: (id: string | null) => void;
  onPersonDragStart: (person: OrgChartPerson) => void;
  onDropPerson: (target: OrgChartTeamColumn) => void;
}) {
  const isOver = dropTargetId === team.team_id;

  return (
    <Box
      onDragOver={(event) => {
        if (!canEdit) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        setDropTargetId(team.team_id);
      }}
      onDragLeave={() => {
        if (dropTargetId === team.team_id) setDropTargetId(null);
      }}
      onDrop={(event) => {
        if (!canEdit) return;
        event.preventDefault();
        setDropTargetId(null);
        onDropPerson(team);
      }}
      sx={{
        width: { xs: 280, sm: 300 },
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 3,
        border: '1px solid',
        borderColor: isOver ? team.colour : 'divider',
        bgcolor: isOver ? `${team.colour}12` : 'background.default',
        boxShadow: isOver ? 4 : 0,
        transition: 'background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease',
        minHeight: 360,
      }}
    >
      <Box
        sx={{
          px: 2,
          py: 1.5,
          borderBottom: '1px solid',
          borderColor: 'divider',
          background: `linear-gradient(135deg, ${team.colour}22 0%, transparent 70%)`,
        }}
      >
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: team.colour,
              flexShrink: 0,
            }}
          />
          <Typography variant="subtitle1" sx={{ fontWeight: 800, flex: 1 }} noWrap>
            {team.team_name}
          </Typography>
          <Chip label={team.member_count} size="small" sx={{ height: 22, fontWeight: 700 }} />
        </Stack>
        <Typography variant="caption" color="text.secondary" noWrap sx={{ mt: 0.5, display: 'block' }}>
          {team.team_lead_name ? `Lead · ${team.team_lead_name}` : 'No team lead'}
        </Typography>
      </Box>

      <Stack spacing={1.25} sx={{ p: 1.5, flex: 1 }}>
        {team.people.length === 0 ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              py: 4,
              textAlign: 'center',
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: 2,
            }}
          >
            {canEdit ? 'Drop a card here' : 'No primary members'}
          </Typography>
        ) : (
          team.people.map((person) => (
            <PersonCard
              key={person.user_id}
              person={person}
              accent={team.colour}
              canEdit={canEdit}
              onDragStart={onPersonDragStart}
            />
          ))
        )}
      </Stack>
    </Box>
  );
}

export function OrganizationChartPage() {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const canEdit = isAdminRole(user?.role_name ?? '');

  const [dragPerson, setDragPerson] = useState<OrgChartPerson | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingMove | null>(null);
  const [effectiveFrom, setEffectiveFrom] = useState(todayIso());
  const [updateManager, setUpdateManager] = useState(true);

  const chartQuery = useQuery({
    queryKey: ORG_CHART_KEY,
    queryFn: () => teamsApi.organizationChart(),
  });

  const moveMutation = useMutation({
    mutationFn: async () => {
      if (!pending) throw new Error('No pending move');
      const { person, targetTeam } = pending;
      if (person.source_team_id && person.member_id) {
        return teamsApi.transferMember(person.source_team_id, person.member_id, {
          target_team_id: targetTeam.team_id,
          effective_from: effectiveFrom || undefined,
          update_reporting_manager: updateManager,
        });
      }
      return teamsApi.assignPrimary(targetTeam.team_id, {
        user_id: person.user_id,
        effective_from: effectiveFrom || undefined,
        update_reporting_manager: updateManager,
      });
    },
    onSuccess: async () => {
      const name = pending?.person.name ?? 'Resource';
      const teamName = pending?.targetTeam.team_name ?? 'team';
      showSuccess(
        `${name} → ${teamName} from ${effectiveFrom}. Primary home and P&L salary split update across the app.`,
      );
      setPending(null);
      setDragPerson(null);
      await queryClient.invalidateQueries({ queryKey: ORG_CHART_KEY });
      await queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
    onError: (error) => {
      showError(getErrorMessage(error));
    },
  });

  const handleDropOnTeam = useCallback(
    (target: OrgChartTeamColumn) => {
      if (!dragPerson) return;
      if (dragPerson.source_team_id === target.team_id) {
        setDragPerson(null);
        return;
      }
      setEffectiveFrom(todayIso());
      setUpdateManager(true);
      setPending({ person: dragPerson, targetTeam: target });
    },
    [dragPerson],
  );

  const unassignedColumn = useMemo((): OrgChartTeamColumn | null => {
    const rows = chartQuery.data?.unassigned ?? [];
    if (rows.length === 0) return null;
    return {
      team_id: '__unassigned__',
      team_name: 'Unassigned',
      colour: '#78909c',
      team_lead_id: null,
      team_lead_name: null,
      member_count: rows.length,
      people: rows,
    };
  }, [chartQuery.data?.unassigned]);

  return (
    <Box>
      <PageHeader
        subtitle="Drag person cards between teams. Moves record an effective-from date so salary is prorated for P&L by calendar days — the same dated transfer used throughout ProTrack."
        action={
          <Button
            startIcon={<RefreshIcon />}
            onClick={() => void chartQuery.refetch()}
            disabled={chartQuery.isFetching}
          >
            Refresh
          </Button>
        }
      />

      <Typography variant="h5" sx={{ fontWeight: 800, mb: 0.5 }}>
        Organization Chart
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {chartQuery.data?.note ??
          (canEdit
            ? 'Admin: drop a card on a team column, confirm the effective date, then save.'
            : 'View limited to your division or teams you lead. Ask an Admin to move resources.')}
      </Typography>

      {chartQuery.isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : chartQuery.isError ? (
        <Alert severity="error">{getErrorMessage(chartQuery.error)}</Alert>
      ) : (chartQuery.data?.teams.length ?? 0) === 0 &&
        (chartQuery.data?.unassigned.length ?? 0) === 0 ? (
        <Alert severity="info">
          {chartQuery.data?.note ||
            'No teams are in your organization-chart scope. Engineering Managers see their division; team leaders see only teams they lead.'}
        </Alert>
      ) : (
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            overflowX: 'auto',
            pb: 2,
            pt: 0.5,
            px: 0.5,
          }}
        >
          {(chartQuery.data?.teams ?? []).map((team) => (
            <TeamColumn
              key={team.team_id}
              team={team}
              canEdit={canEdit}
              dropTargetId={dropTargetId}
              setDropTargetId={setDropTargetId}
              onPersonDragStart={setDragPerson}
              onDropPerson={handleDropOnTeam}
            />
          ))}
          {unassignedColumn ? (
            <Box
              sx={{
                width: { xs: 280, sm: 300 },
                flexShrink: 0,
                borderRadius: 3,
                border: '1px dashed',
                borderColor: 'divider',
                minHeight: 360,
                opacity: 0.95,
              }}
            >
              <Box sx={{ px: 2, py: 1.5, borderBottom: '1px dashed', borderColor: 'divider' }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                  Unassigned
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Drag onto a team to set primary home
                </Typography>
              </Box>
              <Stack spacing={1.25} sx={{ p: 1.5 }}>
                {unassignedColumn.people.map((person) => (
                  <PersonCard
                    key={person.user_id}
                    person={person}
                    accent="#78909c"
                    canEdit={canEdit}
                    onDragStart={setDragPerson}
                  />
                ))}
              </Stack>
            </Box>
          ) : null}
        </Box>
      )}

      <Dialog open={pending != null} onClose={() => !moveMutation.isPending && setPending(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Confirm resource move</DialogTitle>
        <DialogContent>
          {pending ? (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Alert severity="info">
                Moving <strong>{pending.person.name}</strong> to{' '}
                <strong>{pending.targetTeam.team_name}</strong>. Last day on the previous team is the day
                before the effective date; salary splits by calendar days for P&L.
              </Alert>
              <TextField
                label="Effective from"
                type="date"
                value={effectiveFrom}
                onChange={(event) => setEffectiveFrom(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                fullWidth
                required
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={updateManager}
                    onChange={(event) => setUpdateManager(event.target.checked)}
                  />
                }
                label={
                  pending.targetTeam.team_lead_name
                    ? `Update reporting manager to ${pending.targetTeam.team_lead_name}`
                    : 'Update reporting manager to team lead (none set)'
                }
              />
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPending(null)} disabled={moveMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => moveMutation.mutate()}
            disabled={moveMutation.isPending || !effectiveFrom}
          >
            {moveMutation.isPending ? 'Saving…' : 'Confirm move'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default OrganizationChartPage;
