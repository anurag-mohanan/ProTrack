import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
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
  Switch,
  TextField,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/common/PageHeader';
import { teamsApi } from '../api/resources';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { isAdminRole, ROLES } from '../utils/permissions';
import type { OrgChartDepartment, OrgChartPerson, OrgChartTeamColumn } from '../types/Team';

const ORG_CHART_KEY = ['teams', 'organization-chart'] as const;
const VIEW_PREFS_KEY = 'protrack.orgChart.viewPrefs.v2';

type PendingMove = {
  person: OrgChartPerson;
  targetTeam: OrgChartTeamColumn;
};

type TreeNode = {
  person: OrgChartPerson;
  children: TreeNode[];
};

type ViewPrefs = {
  hidePlanningBoard: boolean;
  hideSystemAdmin: boolean;
  hideEmptyDepartments: boolean;
};

const DEFAULT_VIEW_PREFS: ViewPrefs = {
  hidePlanningBoard: true,
  hideSystemAdmin: true,
  hideEmptyDepartments: false,
};

function loadViewPrefs(): ViewPrefs {
  try {
    const raw = localStorage.getItem(VIEW_PREFS_KEY);
    if (!raw) return DEFAULT_VIEW_PREFS;
    return { ...DEFAULT_VIEW_PREFS, ...(JSON.parse(raw) as Partial<ViewPrefs>) };
  } catch {
    return DEFAULT_VIEW_PREFS;
  }
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function isPlanningBoardPerson(person: OrgChartPerson): boolean {
  const role = (person.role_name || '').toLowerCase();
  const name = person.name.toLowerCase();
  const designation = (person.designation || '').toLowerCase();
  return (
    role === ROLES.PLANNING_BOARD.toLowerCase() ||
    name.includes('planning board') ||
    designation.includes('planning board')
  );
}

function isSystemAdminPerson(person: OrgChartPerson): boolean {
  const role = (person.role_name || '').toLowerCase();
  const name = person.name.toLowerCase();
  const email = person.email.toLowerCase();
  return (
    role === ROLES.ADMIN.toLowerCase() ||
    name === 'system admin' ||
    name.startsWith('system admin') ||
    email.startsWith('admin@')
  );
}

function shouldHidePerson(person: OrgChartPerson, prefs: ViewPrefs): boolean {
  if (prefs.hidePlanningBoard && isPlanningBoardPerson(person)) return true;
  if (prefs.hideSystemAdmin && isSystemAdminPerson(person)) return true;
  return false;
}

function filterPeople(people: OrgChartPerson[], prefs: ViewPrefs): OrgChartPerson[] {
  return people.filter((person) => !shouldHidePerson(person, prefs));
}

function filterTeam(team: OrgChartTeamColumn, prefs: ViewPrefs): OrgChartTeamColumn {
  const people = filterPeople(team.people, prefs);
  return { ...team, people, member_count: people.length };
}

function filterDepartment(department: OrgChartDepartment, prefs: ViewPrefs): OrgChartDepartment {
  const leaders = filterPeople(department.leaders, prefs);
  const staff = filterPeople(department.staff, prefs);
  const teams = department.teams
    .map((team) => filterTeam(team, prefs))
    .filter((team) => team.people.length > 0 || !prefs.hideEmptyDepartments);
  const member_count =
    leaders.length + staff.length + teams.reduce((sum, team) => sum + team.member_count, 0);
  return { ...department, leaders, staff, teams, member_count };
}

function BranchChildren({
  accent,
  children,
  wrap = true,
}: {
  accent: string;
  children: ReactNode;
  wrap?: boolean;
}) {
  const childArray = (Array.isArray(children) ? children : [children]).filter(Boolean);
  const count = childArray.length;
  if (count === 0) return null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
      <Box sx={{ width: 2, height: 14, bgcolor: accent, opacity: 0.4 }} />
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          flexWrap: wrap ? 'wrap' : 'nowrap',
          gap: 1.5,
          width: '100%',
          pt: 0.5,
        }}
      >
        {childArray.map((child, index) => (
          <Box key={index} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
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
  featured,
}: {
  person: OrgChartPerson;
  accent: string;
  canEdit: boolean;
  onDragStart: (person: OrgChartPerson) => void;
  isLead?: boolean;
  featured?: boolean;
}) {
  const draggable = canEdit && person.can_move;
  const emphasized = Boolean(isLead || person.is_department_head || featured);
  const title = person.designation || person.role_name || 'Team member';

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
        width: featured ? 240 : '100%',
        maxWidth: featured ? 280 : 280,
        minWidth: featured ? 220 : 0,
        minHeight: featured ? 112 : 100,
        p: featured ? 1.5 : 1.35,
        pl: featured ? 1.75 : 1.6,
        borderRadius: 2.5,
        border: '1px solid',
        borderColor: emphasized ? alpha(accent, 0.55) : alpha('#90a4ae', 0.35),
        bgcolor: 'background.paper',
        boxShadow: emphasized
          ? `0 10px 24px ${alpha(accent, 0.16)}`
          : `0 2px 8px ${alpha('#000', 0.04)}`,
        cursor: draggable ? 'grab' : 'default',
        transition: 'box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease',
        '&:active': draggable ? { cursor: 'grabbing' } : undefined,
        '&:hover': draggable
          ? { boxShadow: `0 12px 28px ${alpha(accent, 0.2)}`, transform: 'translateY(-2px)' }
          : { borderColor: alpha(accent, 0.4) },
        position: 'relative',
        overflow: 'visible',
        boxSizing: 'border-box',
        '&::before': {
          content: '""',
          position: 'absolute',
          left: 0,
          top: 10,
          bottom: 10,
          width: 4,
          borderRadius: '0 4px 4px 0',
          bgcolor: accent,
        },
      }}
    >
      <Stack direction="row" spacing={1.1} sx={{ alignItems: 'flex-start' }}>
        {draggable ? (
          <DragIndicatorIcon sx={{ mt: 0.6, color: 'text.disabled', fontSize: 16, flexShrink: 0 }} />
        ) : null}
        <Avatar
          sx={{
            width: featured ? 42 : 36,
            height: featured ? 42 : 36,
            fontSize: featured ? 14 : 12,
            fontWeight: 700,
            bgcolor: accent,
            flexShrink: 0,
            mt: 0.15,
          }}
        >
          {initials(person.name)}
        </Avatar>
        <Box sx={{ minWidth: 0, flex: 1, overflow: 'visible' }}>
          <Typography
            variant="subtitle2"
            title={person.name}
            sx={{
              fontWeight: 800,
              lineHeight: 1.25,
              fontSize: featured ? 14.5 : 13.5,
              wordBreak: 'break-word',
            }}
          >
            {person.name}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            title={title}
            sx={{
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              lineHeight: 1.35,
              mt: 0.2,
            }}
          >
            {title}
          </Typography>
          <Stack direction="row" spacing={0.5} useFlexGap sx={{ mt: 0.75, flexWrap: 'wrap' }}>
            {person.is_department_head || featured ? (
              <Chip
                label="Dept head"
                size="small"
                sx={{ height: 20, fontSize: 10.5, fontWeight: 700, bgcolor: alpha(accent, 0.16) }}
              />
            ) : isLead ? (
              <Chip
                label="Lead"
                size="small"
                sx={{ height: 20, fontSize: 10.5, fontWeight: 700, bgcolor: alpha(accent, 0.14) }}
              />
            ) : person.is_leadership ? (
              <Chip label="Leader" size="small" variant="outlined" sx={{ height: 20, fontSize: 10.5 }} />
            ) : null}
            {person.stream_name ? (
              <Chip
                label={person.stream_name}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: 10.5 }}
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
        alignItems: 'stretch',
        width: '100%',
        p: 1.5,
        borderRadius: 2.5,
        border: '1px solid',
        borderColor: isOver ? line : alpha(line, 0.28),
        bgcolor: isOver ? alpha(line, 0.08) : alpha(line, 0.04),
        boxShadow: isOver ? 3 : 0,
        transition: 'border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease',
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1.25 }}>
        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: line, flexShrink: 0 }} />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 800 }} noWrap>
            {team.team_name}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {team.team_lead_name ? `Lead · ${team.team_lead_name}` : 'No team lead'}
            {canEdit ? ' · drop cards here' : ''}
          </Typography>
        </Box>
        <Chip label={team.member_count} size="small" sx={{ height: 22, fontWeight: 700 }} />
      </Stack>

      {forest.length === 0 ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            py: 2.5,
            border: '1px dashed',
            borderColor: 'divider',
            borderRadius: 2,
            textAlign: 'center',
          }}
        >
          {canEdit ? 'Drop a person card onto this team' : 'No members'}
        </Typography>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(212px, 1fr))',
            gap: 1.5,
          }}
        >
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
        </Box>
      )}
    </Box>
  );
}

function DepartmentSection({
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
  const accent = department.colour;
  const pool = [...department.leaders, ...department.staff];
  const head =
    pool.find((row) => row.is_department_head) ??
    (department.head_user_id
      ? pool.find((row) => row.user_id === department.head_user_id)
      : undefined);
  const hqPeople = pool.filter((row) => row.user_id !== head?.user_id);
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
        borderColor: alpha(accent, 0.22),
        overflow: 'visible',
        bgcolor: theme.palette.background.paper,
        boxShadow: `0 1px 2px ${alpha('#000', 0.04)}`,
      }}
    >
      <Box
        sx={{
          px: { xs: 2, md: 2.5 },
          py: 1.75,
          borderBottom: '1px solid',
          borderColor: alpha(accent, 0.14),
          background: `linear-gradient(90deg, ${alpha(accent, 0.12)} 0%, ${alpha(
            accent,
            0.03,
          )} 55%, transparent 100%)`,
        }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 800, color: accent, lineHeight: 1.25 }}>
              {department.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
              {isEmpty
                ? department.description || 'Reserved for future expansion'
                : department.head_name
                  ? `Head · ${department.head_name}${department.head_title ? ` · ${department.head_title}` : ''}`
                  : department.description || `${department.member_count} people`}
            </Typography>
          </Box>
          <Chip
            label={isEmpty ? 'Future' : `${department.member_count} people`}
            size="small"
            sx={{
              fontWeight: 700,
              bgcolor: alpha(accent, 0.12),
              alignSelf: { xs: 'flex-start', sm: 'center' },
            }}
          />
        </Stack>
      </Box>

      <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2.25 }}>
        {isEmpty ? (
          <Box
            sx={{
              py: 2.75,
              px: 2,
              borderRadius: 2.5,
              border: '1px dashed',
              borderColor: alpha(accent, 0.35),
              textAlign: 'center',
              color: 'text.secondary',
              bgcolor: alpha(accent, 0.03),
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              No people assigned yet
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
              This department is ready for future org growth.
            </Typography>
          </Box>
        ) : (
          <Stack spacing={2.25}>
            {head ? (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ letterSpacing: 1, color: 'text.secondary', fontWeight: 700 }}
                >
                  Department head
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
                  <PersonCard
                    person={head}
                    accent={accent}
                    canEdit={canEdit}
                    onDragStart={onPersonDragStart}
                    featured
                  />
                </Box>
              </Box>
            ) : null}

            {hqPeople.length > 0 ? (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ letterSpacing: 1, color: 'text.secondary', fontWeight: 700 }}
                >
                  {department.code === 'engineering' ? 'Leadership & HQ' : 'Department staff'}
                </Typography>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(212px, 1fr))',
                    gap: 1.5,
                    mt: 1,
                  }}
                >
                  {hqPeople.map((person) => (
                    <PersonCard
                      key={person.user_id}
                      person={person}
                      accent={accent}
                      canEdit={canEdit}
                      onDragStart={onPersonDragStart}
                      isLead={person.is_leadership}
                    />
                  ))}
                </Box>
              </Box>
            ) : null}

            {department.teams.length > 0 ? (
              <Box>
                <Typography
                  variant="overline"
                  sx={{ letterSpacing: 1, color: 'text.secondary', fontWeight: 700 }}
                >
                  Delivery teams
                </Typography>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: {
                      xs: '1fr',
                      lg: 'repeat(2, minmax(0, 1fr))',
                    },
                    gap: 1.75,
                    mt: 1,
                  }}
                >
                  {department.teams.map((team) => (
                    <TeamBranch
                      key={team.team_id}
                      team={team}
                      canEdit={canEdit}
                      dropTargetId={dropTargetId}
                      setDropTargetId={setDropTargetId}
                      onPersonDragStart={onPersonDragStart}
                      onDropPerson={onDropPerson}
                      accent={accent}
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
  const [viewPrefs, setViewPrefs] = useState<ViewPrefs>(() => loadViewPrefs());

  useEffect(() => {
    localStorage.setItem(VIEW_PREFS_KEY, JSON.stringify(viewPrefs));
  }, [viewPrefs]);

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

  const filteredDepartments = useMemo(() => {
    const departments = (chartQuery.data?.departments ?? []).map((department) =>
      filterDepartment(department, viewPrefs),
    );
    if (!viewPrefs.hideEmptyDepartments) return departments;
    return departments.filter(
      (department) =>
        department.member_count > 0 ||
        department.leaders.length > 0 ||
        department.staff.length > 0 ||
        department.teams.length > 0,
    );
  }, [chartQuery.data?.departments, viewPrefs]);

  const unassigned = useMemo(
    () => filterPeople(chartQuery.data?.unassigned ?? [], viewPrefs),
    [chartQuery.data?.unassigned, viewPrefs],
  );
  const legacyTeams = useMemo(
    () => (chartQuery.data?.teams ?? []).map((team) => filterTeam(team, viewPrefs)),
    [chartQuery.data?.teams, viewPrefs],
  );
  const hasDepartmentView = (chartQuery.data?.departments?.length ?? 0) > 0;
  const totalPeople = filteredDepartments.reduce((sum, row) => sum + row.member_count, 0);
  const hiddenCount =
    viewPrefs.hidePlanningBoard || viewPrefs.hideSystemAdmin
      ? 'Service accounts can be shown via View options'
      : null;

  const setPref = (key: keyof ViewPrefs, value: boolean) => {
    setViewPrefs((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Box>
      <PageHeader
        subtitle="Departments stacked for easy scanning — head, leadership, then delivery teams."
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
          mb: 2,
          p: { xs: 2, md: 2.25 },
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
          direction={{ xs: 'column', md: 'row' }}
          spacing={1.5}
          sx={{ alignItems: { md: 'center' }, justifyContent: 'space-between' }}
        >
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: -0.2 }}>
              Organization Chart
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 720 }}>
              {chartQuery.data?.note ??
                (canEdit
                  ? 'Drop a card on a delivery team, confirm the effective date, then save.'
                  : 'View limited to your division or teams you lead.')}
            </Typography>
          </Box>
          {hasDepartmentView ? (
            <Chip
              label={`${filteredDepartments.length} depts · ${totalPeople} people`}
              sx={{ fontWeight: 700, alignSelf: { xs: 'flex-start', md: 'center' } }}
            />
          ) : null}
        </Stack>
      </Box>

      <Box
        sx={{
          mb: 2.5,
          p: 1.5,
          borderRadius: 2.5,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: alpha(theme.palette.background.paper, 0.8),
        }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between', mb: 0.5 }}
        >
          <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
            <VisibilityOffRoundedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
              View options
            </Typography>
          </Stack>
          {hiddenCount ? (
            <Typography variant="caption" color="text.secondary">
              {hiddenCount}
            </Typography>
          ) : null}
        </Stack>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={{ xs: 0, md: 2 }} useFlexGap>
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={viewPrefs.hidePlanningBoard}
                onChange={(event) => setPref('hidePlanningBoard', event.target.checked)}
              />
            }
            label="Hide Planning Board"
          />
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={viewPrefs.hideSystemAdmin}
                onChange={(event) => setPref('hideSystemAdmin', event.target.checked)}
              />
            }
            label="Hide System Admin"
          />
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={viewPrefs.hideEmptyDepartments}
                onChange={(event) => setPref('hideEmptyDepartments', event.target.checked)}
              />
            }
            label="Hide empty departments"
          />
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
      ) : hasDepartmentView && filteredDepartments.length === 0 && unassigned.length === 0 ? (
        <Alert severity="info">
          All departments are hidden by the current view options. Turn off “Hide empty departments”
          or show service accounts to see more.
        </Alert>
      ) : (
        <Stack spacing={2}>
          {hasDepartmentView ? (
            filteredDepartments.map((department) => (
              <DepartmentSection
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
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: '1fr',
                  md: 'repeat(auto-fit, minmax(280px, 1fr))',
                },
                gap: 1.5,
              }}
            >
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
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(212px, 1fr))',
                  gap: 1.5,
                }}
              >
                {unassigned.map((person) => (
                  <PersonCard
                    key={person.user_id}
                    person={person}
                    accent="#78909c"
                    canEdit={canEdit}
                    onDragStart={setDragPerson}
                  />
                ))}
              </Box>
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
