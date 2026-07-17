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
  alpha,
  useTheme,
} from '@mui/material';
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/common/PageHeader';
import { teamsApi } from '../api/resources';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { isAdminRole } from '../utils/permissions';
import type { OrgChartDepartment, OrgChartPerson, OrgChartTeamColumn } from '../types/Team';

const ORG_CHART_KEY = ['teams', 'organization-chart'] as const;

type PendingMove = {
  person: OrgChartPerson;
  targetTeam: OrgChartTeamColumn;
};

type TreeNode = {
  person: OrgChartPerson;
  children: TreeNode[];
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

/** Build a reporting forest so manager → report lines are easy to follow. */
function buildReportingTree(team: OrgChartTeamColumn): TreeNode[] {
  const people = team.people;
  if (people.length === 0) return [];

  const ids = new Set(people.map((row) => row.user_id));
  const leadId =
    team.team_lead_id && ids.has(team.team_lead_id) ? team.team_lead_id : null;

  const parentOf = new Map<string, string | null>();
  for (const person of people) {
    let parent: string | null = null;
    if (
      person.manager_id &&
      ids.has(person.manager_id) &&
      person.manager_id !== person.user_id
    ) {
      parent = person.manager_id;
    } else if (leadId && person.user_id !== leadId) {
      parent = leadId;
    }
    parentOf.set(person.user_id, parent);
  }

  for (const person of people) {
    const seen = new Set<string>();
    let current: string | null = person.user_id;
    while (current) {
      if (seen.has(current)) {
        parentOf.set(person.user_id, null);
        break;
      }
      seen.add(current);
      current = parentOf.get(current) ?? null;
    }
  }

  const childrenMap = new Map<string | null, OrgChartPerson[]>();
  for (const person of people) {
    const parent = parentOf.get(person.user_id) ?? null;
    const list = childrenMap.get(parent) ?? [];
    list.push(person);
    childrenMap.set(parent, list);
  }

  const nest = (person: OrgChartPerson): TreeNode => {
    const kids = [...(childrenMap.get(person.user_id) ?? [])].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
    return { person, children: kids.map(nest) };
  };

  return [...(childrenMap.get(null) ?? [])]
    .sort((a, b) => {
      if (leadId) {
        if (a.user_id === leadId) return -1;
        if (b.user_id === leadId) return 1;
      }
      return a.name.localeCompare(b.name);
    })
    .map(nest);
}

function PersonCard({
  person,
  accent,
  canEdit,
  onDragStart,
  isLead,
}: {
  person: OrgChartPerson;
  accent: string;
  canEdit: boolean;
  onDragStart: (person: OrgChartPerson) => void;
  isLead?: boolean;
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
        width: 220,
        p: 1.25,
        borderRadius: 2.5,
        border: '1px solid',
        borderColor: isLead || person.is_department_head ? accent : 'divider',
        bgcolor: 'background.paper',
        boxShadow: isLead || person.is_department_head ? `0 0 0 1px ${accent}55` : 1,
        cursor: draggable ? 'grab' : 'default',
        transition: 'box-shadow 0.15s ease, transform 0.15s ease',
        '&:active': draggable ? { cursor: 'grabbing' } : undefined,
        '&:hover': draggable ? { boxShadow: 4, transform: 'translateY(-1px)' } : undefined,
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
      <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
        {draggable ? (
          <DragIndicatorIcon sx={{ mt: 0.35, color: 'text.disabled', fontSize: 16 }} />
        ) : null}
        <Avatar sx={{ width: 34, height: 34, fontSize: 12, fontWeight: 700, bgcolor: accent }}>
          {initials(person.name)}
        </Avatar>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 800, lineHeight: 1.2 }} noWrap>
            {person.name}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
            {person.designation || person.role_name || 'Team member'}
          </Typography>
          <Stack direction="row" spacing={0.5} useFlexGap sx={{ mt: 0.5, flexWrap: 'wrap' }}>
            {person.is_department_head ? (
              <Chip label="Dept head" size="small" sx={{ height: 20, bgcolor: `${accent}22` }} />
            ) : isLead ? (
              <Chip label="Lead" size="small" sx={{ height: 20, bgcolor: `${accent}22` }} />
            ) : person.is_leadership ? (
              <Chip label="Leadership" size="small" variant="outlined" sx={{ height: 20 }} />
            ) : null}
            {person.stream_name ? (
              <Chip label={person.stream_name} size="small" variant="outlined" sx={{ height: 20 }} />
            ) : null}
          </Stack>
          {person.manager_name ? (
            <Typography variant="caption" color="text.secondary" noWrap sx={{ mt: 0.4, display: 'block' }}>
              → {person.manager_name}
            </Typography>
          ) : null}
        </Box>
      </Stack>
    </Box>
  );
}

function TreeBranch({
  node,
  accent,
  teamLeadId,
  canEdit,
  onDragStart,
}: {
  node: TreeNode;
  accent: string;
  teamLeadId: string | null;
  canEdit: boolean;
  onDragStart: (person: OrgChartPerson) => void;
}) {
  const hasChildren = node.children.length > 0;

  return (
    <Box
      component="li"
      sx={{
        listStyle: 'none',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        position: 'relative',
        px: 1.25,
        pt: 2,
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: '50%',
          width: 0,
          height: 16,
          borderLeft: '2px solid',
          borderColor: accent,
          opacity: 0.55,
          transform: 'translateX(-50%)',
        },
      }}
    >
      <PersonCard
        person={node.person}
        accent={accent}
        canEdit={canEdit}
        onDragStart={onDragStart}
        isLead={teamLeadId === node.person.user_id}
      />
      {hasChildren ? (
        <Box
          component="ul"
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            p: 0,
            m: 0,
            pt: 2,
            position: 'relative',
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: '50%',
              width: 0,
              height: 16,
              borderLeft: '2px solid',
              borderColor: accent,
              opacity: 0.55,
              transform: 'translateX(-50%)',
            },
          }}
        >
          {node.children.map((child, index) => (
            <Box
              key={child.person.user_id}
              sx={{
                position: 'relative',
                '&::before':
                  node.children.length > 1
                    ? {
                        content: '""',
                        position: 'absolute',
                        top: 0,
                        left: index === 0 ? '50%' : 0,
                        right: index === node.children.length - 1 ? '50%' : 0,
                        height: 0,
                        borderTop: '2px solid',
                        borderColor: accent,
                        opacity: 0.45,
                      }
                    : undefined,
              }}
            >
              <TreeBranch
                node={child}
                accent={accent}
                teamLeadId={teamLeadId}
                canEdit={canEdit}
                onDragStart={onDragStart}
              />
            </Box>
          ))}
        </Box>
      ) : null}
    </Box>
  );
}

function TeamTree({
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
  const forest = useMemo(() => buildReportingTree(team), [team]);

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
        minWidth: 280,
        flex: '1 1 320px',
        maxWidth: 720,
        borderRadius: 3,
        border: '1px solid',
        borderColor: isOver ? team.colour : 'divider',
        bgcolor: isOver ? `${team.colour}10` : alpha('#fff', 0.55),
        boxShadow: isOver ? 4 : 0,
        overflow: 'hidden',
        transition: 'border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease',
      }}
    >
      <Box
        sx={{
          px: 2,
          py: 1.5,
          borderBottom: '1px solid',
          borderColor: 'divider',
          background: `linear-gradient(120deg, ${team.colour}28 0%, transparent 65%)`,
        }}
      >
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: team.colour, flexShrink: 0 }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 800, flex: 1 }} noWrap>
            {team.team_name}
          </Typography>
          <Chip label={team.member_count} size="small" sx={{ height: 22, fontWeight: 700 }} />
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.35 }}>
          {team.team_lead_name ? `Lead · ${team.team_lead_name}` : 'No team lead'}
          {canEdit ? ' · drop a card here to move' : ''}
        </Typography>
      </Box>

      <Box sx={{ px: 1, py: 2, overflowX: 'auto' }}>
        {forest.length === 0 ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              py: 4,
              textAlign: 'center',
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: 2,
              mx: 1,
            }}
          >
            {canEdit ? 'Drop a person card onto this team' : 'No primary members'}
          </Typography>
        ) : (
          <Box
            component="ul"
            sx={{
              display: 'flex',
              justifyContent: 'center',
              flexWrap: 'wrap',
              p: 0,
              m: 0,
              listStyle: 'none',
            }}
          >
            {forest.map((root) => (
              <Box key={root.person.user_id} component="li" sx={{ listStyle: 'none' }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <PersonCard
                    person={root.person}
                    accent={team.colour}
                    canEdit={canEdit}
                    onDragStart={onPersonDragStart}
                    isLead={team.team_lead_id === root.person.user_id}
                  />
                  {root.children.length > 0 ? (
                    <Box
                      component="ul"
                      sx={{
                        display: 'flex',
                        justifyContent: 'center',
                        flexWrap: 'wrap',
                        p: 0,
                        m: 0,
                        pt: 2,
                        position: 'relative',
                        '&::before': {
                          content: '""',
                          position: 'absolute',
                          top: 0,
                          left: '50%',
                          height: 16,
                          borderLeft: '2px solid',
                          borderColor: team.colour,
                          opacity: 0.55,
                          transform: 'translateX(-50%)',
                        },
                      }}
                    >
                      {root.children.map((child, index) => (
                        <Box
                          key={child.person.user_id}
                          sx={{
                            position: 'relative',
                            '&::before':
                              root.children.length > 1
                                ? {
                                    content: '""',
                                    position: 'absolute',
                                    top: 0,
                                    left: index === 0 ? '50%' : 0,
                                    right: index === root.children.length - 1 ? '50%' : 0,
                                    borderTop: '2px solid',
                                    borderColor: team.colour,
                                    opacity: 0.45,
                                  }
                                : undefined,
                          }}
                        >
                          <TreeBranch
                            node={child}
                            accent={team.colour}
                            teamLeadId={team.team_lead_id}
                            canEdit={canEdit}
                            onDragStart={onPersonDragStart}
                          />
                        </Box>
                      ))}
                    </Box>
                  ) : null}
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}

function DepartmentPanel({
  department,
  canEdit,
  dropTargetId,
  setDropTargetId,
  onPersonDragStart,
  onDropPerson,
}: {
  department: OrgChartDepartment;
  canEdit: boolean;
  dropTargetId: string | null;
  setDropTargetId: (id: string | null) => void;
  onPersonDragStart: (person: OrgChartPerson) => void;
  onDropPerson: (target: OrgChartTeamColumn) => void;
}) {
  const theme = useTheme();
  const isEmpty =
    department.member_count === 0 &&
    department.leaders.length === 0 &&
    department.staff.length === 0 &&
    department.teams.length === 0;

  return (
    <Box
      sx={{
        borderRadius: 3,
        border: '1px solid',
        borderColor: alpha(department.colour, 0.35),
        overflow: 'hidden',
        background: `linear-gradient(160deg, ${alpha(department.colour, 0.1)} 0%, ${alpha(
          theme.palette.background.paper,
          0.96,
        )} 42%, ${theme.palette.background.default} 100%)`,
      }}
    >
      <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2 }}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', minWidth: 0 }}>
            <Box
              sx={{
                width: 42,
                height: 42,
                borderRadius: 2,
                display: 'grid',
                placeItems: 'center',
                bgcolor: alpha(department.colour, 0.18),
                color: department.colour,
                flexShrink: 0,
              }}
            >
              <AccountTreeRoundedIcon fontSize="small" />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6" sx={{ fontWeight: 800, lineHeight: 1.2 }} noWrap>
                {department.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {department.head_name
                  ? `Head · ${department.head_name}${department.head_title ? ` · ${department.head_title}` : ''}`
                  : department.description || 'Ready for future expansion'}
              </Typography>
            </Box>
          </Stack>
          <Chip
            label={`${department.member_count} people`}
            size="small"
            sx={{ fontWeight: 700, bgcolor: alpha(department.colour, 0.14) }}
          />
        </Stack>
      </Box>

      <Box sx={{ px: { xs: 2, md: 2.5 }, pb: 2.5 }}>
        {isEmpty ? (
          <Box
            sx={{
              py: 3.5,
              px: 2,
              borderRadius: 2.5,
              border: '1px dashed',
              borderColor: alpha(department.colour, 0.35),
              textAlign: 'center',
              color: 'text.secondary',
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              No people assigned yet
            </Typography>
            <Typography variant="caption" sx={{ mt: 0.5, display: 'block' }}>
              This department is reserved for future org growth.
            </Typography>
          </Box>
        ) : (
          <Stack spacing={2.25}>
            {(department.leaders.length > 0 || department.staff.length > 0) && (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ letterSpacing: 1.1, color: 'text.secondary', fontWeight: 700 }}
                >
                  {department.code === 'engineering' ? 'Leadership & HQ' : 'Department staff'}
                </Typography>
                <Stack direction="row" spacing={1.25} useFlexGap sx={{ flexWrap: 'wrap', mt: 1 }}>
                  {[...department.leaders, ...department.staff].map((person) => (
                    <PersonCard
                      key={person.user_id}
                      person={person}
                      accent={department.colour}
                      canEdit={canEdit}
                      onDragStart={onPersonDragStart}
                      isLead={person.is_department_head}
                    />
                  ))}
                </Stack>
              </Box>
            )}

            {department.teams.length > 0 ? (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ letterSpacing: 1.1, color: 'text.secondary', fontWeight: 700 }}
                >
                  Delivery teams
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 2,
                    mt: 1,
                  }}
                >
                  {department.teams.map((team) => (
                    <TeamTree
                      key={team.team_id}
                      team={team}
                      canEdit={canEdit}
                      dropTargetId={dropTargetId}
                      setDropTargetId={setDropTargetId}
                      onPersonDragStart={onPersonDragStart}
                      onDropPerson={onDropPerson}
                    />
                  ))}
                </Box>
              </Box>
            ) : null}
          </Stack>
        )}
      </Box>
    </Box>
  );
}

export function OrganizationChartPage() {
  const theme = useTheme();
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

  const departments = chartQuery.data?.departments ?? [];
  const unassigned = chartQuery.data?.unassigned ?? [];
  const legacyTeams = chartQuery.data?.teams ?? [];
  const hasDepartmentView = departments.length > 0;

  return (
    <Box>
      <PageHeader
        subtitle="Company departments → leadership → delivery teams. Finance primary homes stay dated for P&L."
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

      <Box
        sx={{
          mb: 2.5,
          p: { xs: 2, md: 2.5 },
          borderRadius: 3,
          background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.1)} 0%, ${alpha(
            theme.palette.info.main,
            0.07,
          )} 55%, ${alpha(theme.palette.background.paper, 0.92)} 100%)`,
          border: '1px solid',
          borderColor: alpha(theme.palette.primary.main, 0.12),
        }}
      >
        <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: -0.2 }}>
          Organization Chart
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, maxWidth: 820 }}>
          {chartQuery.data?.note ??
            (canEdit
              ? 'Drop a card on a delivery team, confirm the effective date, then save.'
              : 'View limited to your division or teams you lead.')}
        </Typography>
      </Box>

      {chartQuery.isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : chartQuery.isError ? (
        <Alert severity="error">{getErrorMessage(chartQuery.error)}</Alert>
      ) : !hasDepartmentView && legacyTeams.length === 0 && unassigned.length === 0 ? (
        <Alert severity="info">
          {chartQuery.data?.note ||
            'No teams are in your organization-chart scope. Engineering Managers see their division; team leaders see only teams they lead.'}
        </Alert>
      ) : (
        <Stack spacing={2.5}>
          {hasDepartmentView ? (
            departments.map((department) => (
              <DepartmentPanel
                key={department.department_id}
                department={department}
                canEdit={canEdit}
                dropTargetId={dropTargetId}
                setDropTargetId={setDropTargetId}
                onPersonDragStart={setDragPerson}
                onDropPerson={handleDropOnTeam}
              />
            ))
          ) : (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2.5 }}>
              {legacyTeams.map((team) => (
                <TeamTree
                  key={team.team_id}
                  team={team}
                  canEdit={canEdit}
                  dropTargetId={dropTargetId}
                  setDropTargetId={setDropTargetId}
                  onPersonDragStart={setDragPerson}
                  onDropPerson={handleDropOnTeam}
                />
              ))}
            </Box>
          )}

          {canEdit && unassigned.length > 0 ? (
            <Box
              sx={{
                borderRadius: 3,
                border: '1px dashed',
                borderColor: 'divider',
                p: 2,
                bgcolor: alpha(theme.palette.warning.main, 0.04),
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 0.5 }}>
                Unassigned
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                Drag onto a delivery team to set primary home
              </Typography>
              <Stack direction="row" spacing={1.25} useFlexGap sx={{ flexWrap: 'wrap' }}>
                {unassigned.map((person) => (
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
        </Stack>
      )}

      <Dialog
        open={pending != null}
        onClose={() => !moveMutation.isPending && setPending(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Confirm resource move</DialogTitle>
        <DialogContent>
          {pending ? (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Alert severity="info">
                Moving <strong>{pending.person.name}</strong> to{' '}
                <strong>{pending.targetTeam.team_name}</strong>. Last day on the previous team is the
                day before the effective date; salary splits by calendar days for P&L.
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
