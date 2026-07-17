import { useCallback, useMemo, useState, type ReactNode } from 'react';
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

/** Vertical stem + optional horizontal span for org-tree branches. */
function BranchChildren({
  accent,
  children,
}: {
  accent: string;
  children: ReactNode;
}) {
  const childArray = (Array.isArray(children) ? children : [children]).filter(Boolean);
  const count = childArray.length;
  if (count === 0) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: '100%',
      }}
    >
      <Box sx={{ width: 2, height: 18, bgcolor: accent, opacity: 0.45 }} />
      {count > 1 ? (
        <Box
          sx={{
            position: 'relative',
            width: '100%',
            height: 2,
            mb: 0,
            '&::before': {
              content: '""',
              position: 'absolute',
              left: '12.5%',
              right: '12.5%',
              top: 0,
              height: 2,
              bgcolor: accent,
              opacity: 0.35,
            },
          }}
        />
      ) : null}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          flexWrap: 'nowrap',
          gap: 0,
          width: '100%',
          overflowX: 'auto',
          pb: 0.5,
        }}
      >
        {childArray.map((child, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              position: 'relative',
              px: 1.25,
              pt: count > 1 ? 2 : 0,
              '&::before':
                count > 1
                  ? {
                      content: '""',
                      position: 'absolute',
                      top: 0,
                      left: '50%',
                      width: 0,
                      height: 16,
                      borderLeft: '2px solid',
                      borderColor: accent,
                      opacity: 0.45,
                      transform: 'translateX(-50%)',
                    }
                  : undefined,
            }}
          >
            {child}
          </Box>
        ))}
      </Box>
    </Box>
  );
}

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
  compact,
}: {
  person: OrgChartPerson;
  accent: string;
  canEdit: boolean;
  onDragStart: (person: OrgChartPerson) => void;
  isLead?: boolean;
  compact?: boolean;
}) {
  const draggable = canEdit && person.can_move;
  const emphasized = Boolean(isLead || person.is_department_head);

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
        width: compact ? 168 : 200,
        p: compact ? 1 : 1.15,
        borderRadius: 2.5,
        border: '1px solid',
        borderColor: emphasized ? accent : 'divider',
        bgcolor: 'background.paper',
        boxShadow: emphasized ? `0 8px 20px ${alpha(accent, 0.18)}` : 1,
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
          width: 3,
          bgcolor: accent,
        },
      }}
    >
      <Stack direction="row" spacing={0.85} sx={{ alignItems: 'flex-start' }}>
        {draggable ? (
          <DragIndicatorIcon sx={{ mt: 0.25, color: 'text.disabled', fontSize: 15 }} />
        ) : null}
        <Avatar
          sx={{
            width: compact ? 28 : 32,
            height: compact ? 28 : 32,
            fontSize: 11,
            fontWeight: 700,
            bgcolor: accent,
          }}
        >
          {initials(person.name)}
        </Avatar>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 800, lineHeight: 1.15, fontSize: compact ? 12.5 : 13.5 }}
            noWrap
          >
            {person.name}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
            {person.designation || person.role_name || 'Team member'}
          </Typography>
          <Stack direction="row" spacing={0.4} useFlexGap sx={{ mt: 0.4, flexWrap: 'wrap' }}>
            {person.is_department_head ? (
              <Chip label="Head" size="small" sx={{ height: 18, fontSize: 10, bgcolor: `${accent}22` }} />
            ) : isLead ? (
              <Chip label="Lead" size="small" sx={{ height: 18, fontSize: 10, bgcolor: `${accent}22` }} />
            ) : person.is_leadership ? (
              <Chip label="Leader" size="small" variant="outlined" sx={{ height: 18, fontSize: 10 }} />
            ) : null}
            {person.stream_name ? (
              <Chip
                label={person.stream_name}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: 10 }}
              />
            ) : null}
          </Stack>
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
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <PersonCard
        person={node.person}
        accent={accent}
        canEdit={canEdit}
        onDragStart={onDragStart}
        isLead={teamLeadId === node.person.user_id}
        compact
      />
      {node.children.length > 0 ? (
        <BranchChildren accent={accent}>
          {node.children.map((child) => (
            <TreeBranch
              key={child.person.user_id}
              node={child}
              accent={accent}
              teamLeadId={teamLeadId}
              canEdit={canEdit}
              onDragStart={onDragStart}
            />
          ))}
        </BranchChildren>
      ) : null}
    </Box>
  );
}

function TeamBranch({
  team,
  canEdit,
  dropTargetId,
  setDropTargetId,
  onPersonDragStart,
  onDropPerson,
  accent,
}: {
  team: OrgChartTeamColumn;
  canEdit: boolean;
  dropTargetId: string | null;
  setDropTargetId: (id: string | null) => void;
  onPersonDragStart: (person: OrgChartPerson) => void;
  onDropPerson: (target: OrgChartTeamColumn) => void;
  accent: string;
}) {
  const isOver = dropTargetId === team.team_id;
  const forest = useMemo(() => buildReportingTree(team), [team]);
  const line = team.colour || accent;

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
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        minWidth: 200,
        px: 0.5,
        py: 1,
        borderRadius: 2.5,
        border: '1px solid',
        borderColor: isOver ? line : alpha(line, 0.28),
        bgcolor: isOver ? alpha(line, 0.08) : alpha(line, 0.03),
        boxShadow: isOver ? 3 : 0,
        transition: 'border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease',
      }}
    >
      <Box
        sx={{
          px: 1.5,
          py: 0.7,
          mb: 1,
          borderRadius: 999,
          bgcolor: alpha(line, 0.14),
          border: '1px solid',
          borderColor: alpha(line, 0.35),
          textAlign: 'center',
          maxWidth: 220,
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 800, display: 'block', lineHeight: 1.2 }} noWrap>
          {team.team_name}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }} noWrap>
          {team.team_lead_name ? `Lead · ${team.team_lead_name}` : 'No team lead'}
          {` · ${team.member_count}`}
        </Typography>
      </Box>

      {forest.length === 0 ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            py: 2,
            px: 1.5,
            border: '1px dashed',
            borderColor: 'divider',
            borderRadius: 2,
            textAlign: 'center',
          }}
        >
          {canEdit ? 'Drop here' : 'Empty'}
        </Typography>
      ) : (
        <BranchChildren accent={line}>
          {forest.map((root) => (
            <TreeBranch
              key={root.person.user_id}
              node={root}
              accent={line}
              teamLeadId={team.team_lead_id}
              canEdit={canEdit}
              onDragStart={onPersonDragStart}
            />
          ))}
        </BranchChildren>
      )}
    </Box>
  );
}

function DepartmentBranch({
  department,
  canEdit,
  dropTargetId,
  setDropTargetId,
  onPersonDragStart,
  onDropPerson,
  isFirst,
  isLast,
  siblingCount,
}: {
  department: OrgChartDepartment;
  canEdit: boolean;
  dropTargetId: string | null;
  setDropTargetId: (id: string | null) => void;
  onPersonDragStart: (person: OrgChartPerson) => void;
  onDropPerson: (target: OrgChartTeamColumn) => void;
  isFirst: boolean;
  isLast: boolean;
  siblingCount: number;
}) {
  const accent = department.colour;
  const head =
    department.leaders.find((row) => row.is_department_head) ??
    (department.head_user_id
      ? department.leaders.find((row) => row.user_id === department.head_user_id)
      : undefined);
  const otherLeaders = department.leaders.filter((row) => row.user_id !== head?.user_id);
  const hqPeople = [...otherLeaders, ...department.staff];
  const isEmpty =
    department.member_count === 0 &&
    department.leaders.length === 0 &&
    department.staff.length === 0 &&
    department.teams.length === 0;

  const midChildren: ReactNode[] = [];
  if (hqPeople.length > 0) {
    midChildren.push(
      <Box key="hq" sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Chip
          label={department.code === 'engineering' ? 'Leadership & HQ' : 'Staff'}
          size="small"
          sx={{ mb: 1, height: 22, fontWeight: 700, bgcolor: alpha(accent, 0.12) }}
        />
        <BranchChildren accent={accent}>
          {hqPeople.map((person) => (
            <PersonCard
              key={person.user_id}
              person={person}
              accent={accent}
              canEdit={canEdit}
              onDragStart={onPersonDragStart}
              isLead={person.is_leadership}
              compact
            />
          ))}
        </BranchChildren>
      </Box>,
    );
  }
  for (const team of department.teams) {
    midChildren.push(
      <TeamBranch
        key={team.team_id}
        team={team}
        canEdit={canEdit}
        dropTargetId={dropTargetId}
        setDropTargetId={setDropTargetId}
        onPersonDragStart={onPersonDragStart}
        onDropPerson={onDropPerson}
        accent={accent}
      />,
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        position: 'relative',
        px: 1.5,
        pt: 2.25,
        minWidth: isEmpty ? 160 : 240,
        '&::before':
          siblingCount > 1
            ? {
                content: '""',
                position: 'absolute',
                top: 0,
                left: isFirst ? '50%' : 0,
                right: isLast ? '50%' : 0,
                height: 2,
                bgcolor: alpha('#546e7a', 0.35),
              }
            : undefined,
        '&::after': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: '50%',
          width: 0,
          height: 18,
          borderLeft: '2px solid',
          borderColor: alpha('#546e7a', 0.45),
          transform: 'translateX(-50%)',
        },
      }}
    >
      {/* Department node */}
      <Box
        sx={{
          px: 2,
          py: 1.1,
          borderRadius: 2.5,
          minWidth: 150,
          textAlign: 'center',
          bgcolor: alpha(accent, 0.12),
          border: '1px solid',
          borderColor: alpha(accent, 0.45),
          boxShadow: `0 10px 24px ${alpha(accent, 0.12)}`,
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 900, letterSpacing: 0.2, color: accent }}>
          {department.name}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          {isEmpty
            ? 'Future expansion'
            : department.head_name
              ? `Head · ${department.head_name}`
              : `${department.member_count} people`}
        </Typography>
      </Box>

      {isEmpty ? null : (
        <BranchChildren accent={accent}>
          {head ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <PersonCard
                person={head}
                accent={accent}
                canEdit={canEdit}
                onDragStart={onPersonDragStart}
                isLead
              />
              {midChildren.length > 0 ? (
                <BranchChildren accent={accent}>{midChildren}</BranchChildren>
              ) : null}
            </Box>
          ) : midChildren.length > 0 ? (
            midChildren
          ) : (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
              No people yet
            </Typography>
          )}
        </BranchChildren>
      )}
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
  const totalPeople = departments.reduce((sum, row) => sum + row.member_count, 0);

  return (
    <Box>
      <PageHeader
        subtitle="Top-down hierarchy: company → departments → heads → leadership → delivery teams."
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
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1.5}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <Box>
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
          {hasDepartmentView ? (
            <Chip
              label={`${departments.length} depts · ${totalPeople} people`}
              sx={{ fontWeight: 700, alignSelf: { xs: 'flex-start', sm: 'center' } }}
            />
          ) : null}
        </Stack>
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
            <Box
              sx={{
                borderRadius: 3,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: alpha(theme.palette.background.paper, 0.7),
                backgroundImage: `radial-gradient(${alpha(theme.palette.primary.main, 0.05)} 1px, transparent 1px)`,
                backgroundSize: '18px 18px',
                p: { xs: 2, md: 3 },
                overflowX: 'auto',
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  minWidth: 'max-content',
                  mx: 'auto',
                }}
              >
                {/* Company root */}
                <Box
                  sx={{
                    px: 3,
                    py: 1.35,
                    borderRadius: 3,
                    bgcolor: theme.palette.primary.main,
                    color: theme.palette.primary.contrastText,
                    boxShadow: `0 12px 28px ${alpha(theme.palette.primary.main, 0.28)}`,
                    textAlign: 'center',
                    minWidth: 200,
                  }}
                >
                  <Typography variant="subtitle1" sx={{ fontWeight: 900, letterSpacing: 0.3 }}>
                    Organization
                  </Typography>
                  <Typography variant="caption" sx={{ opacity: 0.9 }}>
                    Departments · Leadership · Teams
                  </Typography>
                </Box>

                <Box sx={{ width: 2, height: 22, bgcolor: alpha('#546e7a', 0.45) }} />

                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'flex-start',
                    position: 'relative',
                  }}
                >
                  {departments.map((department, index) => (
                    <DepartmentBranch
                      key={department.department_id}
                      department={department}
                      canEdit={canEdit}
                      dropTargetId={dropTargetId}
                      setDropTargetId={setDropTargetId}
                      onPersonDragStart={setDragPerson}
                      onDropPerson={handleDropOnTeam}
                      isFirst={index === 0}
                      isLast={index === departments.length - 1}
                      siblingCount={departments.length}
                    />
                  ))}
                </Box>
              </Box>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2.5, justifyContent: 'center' }}>
              {legacyTeams.map((team) => (
                <TeamBranch
                  key={team.team_id}
                  team={team}
                  canEdit={canEdit}
                  dropTargetId={dropTargetId}
                  setDropTargetId={setDropTargetId}
                  onPersonDragStart={setDragPerson}
                  onDropPerson={handleDropOnTeam}
                  accent={team.colour}
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
                    compact
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
