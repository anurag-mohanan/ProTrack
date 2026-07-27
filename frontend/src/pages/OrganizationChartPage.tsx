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
  IconButton,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader } from '../components/common/PageHeader';
import { orgDepartmentsApi, teamsApi } from '../api/resources';
import { getErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { isAdminRole, ROLES } from '../utils/permissions';
import type { OrgChartDepartment, OrgChartPerson, OrgChartTeamColumn } from '../types/Team';

const ORG_CHART_KEY = ['teams', 'organization-chart'] as const;
const VIEW_PREFS_KEY = 'protrack.orgChart.viewPrefs.v2';

/** Ink & Plate visual tokens — presentation only; does not affect chart logic. */
const orgTokens = {
  radius: { stamp: 4, counter: 6, card: 10, bay: 12, plate: 14 },
  ink: {
    900: '#1f2b38',
    600: '#46586b',
    400: '#8a99a8',
    canvas: '#f6f8fa',
    paper: '#ffffff',
    execSurface: '#fbfcfd',
  },
  border: {
    hair: 'rgba(31,43,56,0.09)',
    mid: 'rgba(31,43,56,0.12)',
    strong: 'rgba(31,43,56,0.16)',
  },
  shadow: {
    member: '0 1px 1px rgba(31,43,56,.04), 0 1px 3px rgba(31,43,56,.05)',
    lead: '0 1px 2px rgba(31,43,56,.05), 0 3px 8px rgba(31,43,56,.05)',
    head: (a: string) => `0 1px 2px rgba(31,43,56,.05), 0 8px 20px ${alpha(a, 0.12)}`,
    exec: '0 1px 2px rgba(31,43,56,.05), 0 12px 28px rgba(31,43,56,.10)',
    lifted: '0 16px 36px rgba(31,43,56,.16)',
  },
  connector: {
    width: '1.5px',
    parentDrop: 16,
    childDrop: 14,
    execSpine: 24,
    ink: 'rgba(31,43,56,0.16)',
  },
  card: {
    w: 232,
    wHead: 264,
    wExec: 296,
    avatar: 34,
    avatarLead: 38,
    avatarHead: 44,
    avatarExec: 56,
  },
  gap: { card: 1.5, team: 2, section: 2.75, dept: 4 },
  motion: '180ms cubic-bezier(0.2, 0, 0.2, 1)',
} as const;

type PersonTier = 'root' | 'head' | 'lead' | 'member';

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

function accentInk(accent: string): string {
  return `color-mix(in srgb, ${accent} 74%, ${orgTokens.ink[900]})`;
}

function SectionEyebrow({ label }: { label: string }) {
  return (
    <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center', mb: 1.25 }}>
      <Typography
        variant="overline"
        sx={{
          letterSpacing: '0.08em',
          color: orgTokens.ink[400],
          fontWeight: 700,
          lineHeight: 1,
          flexShrink: 0,
        }}
      >
        {label}
      </Typography>
      <Box sx={{ flex: 1, height: '1px', bgcolor: orgTokens.border.hair }} />
    </Stack>
  );
}

function RankStamp({ label, accent }: { label: string; accent: string }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        height: 18,
        px: 0.75,
        borderRadius: `${orgTokens.radius.stamp}px`,
        bgcolor: alpha(accent, 0.1),
        color: accentInk(accent),
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        lineHeight: 1,
      }}
    >
      {label}
    </Box>
  );
}

function CountBadge({ label }: { label: string }) {
  return (
    <Box
      sx={{
        px: 1,
        py: 0.35,
        borderRadius: `${orgTokens.radius.counter}px`,
        border: '1px solid',
        borderColor: orgTokens.border.mid,
        bgcolor: 'transparent',
        color: orgTokens.ink[600],
        fontSize: 12,
        fontWeight: 700,
        fontVariantNumeric: 'tabular-nums',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </Box>
  );
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

  const connector = alpha(accent, 0.42);

  return (
    <Box
      sx={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: '100%',
        pt: `${orgTokens.connector.parentDrop + orgTokens.connector.childDrop}px`,
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: '50%',
          width: orgTokens.connector.width,
          height: orgTokens.connector.parentDrop,
          bgcolor: connector,
          transform: 'translateX(-50%)',
        },
      }}
    >
      {count > 1 ? (
        <Box
          sx={{
            position: 'absolute',
            top: orgTokens.connector.parentDrop,
            left: '12%',
            right: '12%',
            height: orgTokens.connector.width,
            bgcolor: connector,
            borderRadius: '1px',
          }}
        />
      ) : null}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          flexWrap: wrap ? 'wrap' : 'nowrap',
          gap: orgTokens.gap.card,
          width: '100%',
        }}
      >
        {childArray.map((child, index) => (
          <Box
            key={index}
            sx={{
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              '&::before': {
                content: '""',
                position: 'absolute',
                top: -orgTokens.connector.childDrop,
                left: '50%',
                width: orgTokens.connector.width,
                height: orgTokens.connector.childDrop,
                bgcolor: connector,
                transform: 'translateX(-50%)',
              },
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

function resolveTier(args: {
  featured?: boolean;
  isLead?: boolean;
  person: OrgChartPerson;
  executive?: boolean;
}): PersonTier {
  if (args.executive) return 'root';
  if (args.featured || args.person.is_department_head) return 'head';
  if (args.isLead || args.person.is_leadership) return 'lead';
  return 'member';
}

function PersonCard({
  person,
  accent,
  canEdit,
  onDragStart,
  isLead,
  featured,
  executive,
}: {
  person: OrgChartPerson;
  accent: string;
  canEdit: boolean;
  onDragStart: (person: OrgChartPerson) => void;
  isLead?: boolean;
  featured?: boolean;
  executive?: boolean;
}) {
  const draggable = canEdit && person.can_move;
  const tier = resolveTier({ featured, isLead, person, executive });
  const title = person.designation || person.role_name || 'Team member';
  const inkAccent = executive ? orgTokens.ink[900] : accent;

  const width =
    tier === 'root'
      ? orgTokens.card.wExec
      : tier === 'head'
        ? orgTokens.card.wHead
        : orgTokens.card.w;
  const avatarSize =
    tier === 'root'
      ? orgTokens.card.avatarExec
      : tier === 'head'
        ? orgTokens.card.avatarHead
        : tier === 'lead'
          ? orgTokens.card.avatarLead
          : orgTokens.card.avatar;
  const flagWidth = tier === 'root' || tier === 'head' ? 4 : tier === 'lead' ? 3 : 2;
  const nameSize = tier === 'root' ? 17 : tier === 'head' ? 15 : tier === 'lead' ? 14 : 13.5;
  const nameWeight = tier === 'root' || tier === 'head' ? 700 : tier === 'lead' ? 650 : 600;
  const solidAvatar = tier === 'root' || tier === 'head';
  const stampLabel =
    tier === 'root'
      ? person.designation || person.role_name || 'Organization head'
      : person.is_department_head || featured
        ? 'Dept head'
        : isLead
          ? 'Lead'
          : person.is_leadership
            ? 'Leader'
            : null;

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
        width: featured || executive ? width : '100%',
        maxWidth: width,
        minWidth: featured || executive ? width - 24 : 0,
        p: tier === 'root' ? '20px 22px' : tier === 'head' ? '16px 18px 16px 20px' : '12px 14px 12px 16px',
        borderRadius: `${orgTokens.radius.card}px`,
        border: executive ? '2px solid' : '1px solid',
        borderColor: executive
          ? orgTokens.border.strong
          : tier === 'head'
            ? alpha(accent, 0.42)
            : tier === 'lead'
              ? alpha(accent, 0.28)
              : orgTokens.border.mid,
        bgcolor: executive ? orgTokens.ink.execSurface : orgTokens.ink.paper,
        boxShadow:
          tier === 'root'
            ? orgTokens.shadow.exec
            : tier === 'head'
              ? orgTokens.shadow.head(accent)
              : tier === 'lead'
                ? orgTokens.shadow.lead
                : orgTokens.shadow.member,
        cursor: draggable ? 'grab' : 'default',
        transition: `box-shadow ${orgTokens.motion}, transform ${orgTokens.motion}, border-color ${orgTokens.motion}`,
        '&:active': draggable ? { cursor: 'grabbing' } : undefined,
        '&:hover': draggable
          ? {
              boxShadow: orgTokens.shadow.lifted,
              transform: 'translateY(-2px)',
              borderColor: alpha(inkAccent, 0.55),
              '& .org-drag-grip': { opacity: 1 },
            }
          : { borderColor: alpha(inkAccent, 0.4) },
        position: 'relative',
        overflow: 'hidden',
        boxSizing: 'border-box',
        ...(executive
          ? {
              '&::after': {
                content: '""',
                position: 'absolute',
                left: 0,
                right: 0,
                top: 0,
                height: 2,
                bgcolor: alpha(orgTokens.ink[900], 0.85),
              },
            }
          : {
              '&::before': {
                content: '""',
                position: 'absolute',
                left: 0,
                top: 8,
                bottom: 8,
                width: flagWidth,
                borderRadius: '0 3px 3px 0',
                bgcolor: tier === 'member' ? alpha(accent, 0.4) : alpha(accent, tier === 'lead' ? 0.85 : 1),
              },
            }),
      }}
    >
      <Stack direction="row" spacing={1.1} sx={{ alignItems: 'flex-start' }}>
        <Box
          sx={{
            width: 14,
            flexShrink: 0,
            display: 'flex',
            justifyContent: 'center',
            pt: 0.55,
          }}
        >
          {draggable ? (
            <DragIndicatorIcon
              className="org-drag-grip"
              sx={{
                color: orgTokens.ink[400],
                fontSize: 16,
                opacity: executive ? 0.3 : 0.4,
                transition: `opacity ${orgTokens.motion}`,
              }}
            />
          ) : null}
        </Box>
        <Avatar
          sx={{
            width: avatarSize,
            height: avatarSize,
            fontSize: avatarSize * 0.34,
            fontWeight: 700,
            bgcolor: solidAvatar ? inkAccent : alpha(accent, 0.12),
            color: solidAvatar ? '#fff' : accentInk(accent),
            flexShrink: 0,
            mt: 0.1,
            border: `2px solid ${orgTokens.ink.paper}`,
            boxSizing: 'border-box',
          }}
        >
          {initials(person.name)}
        </Avatar>
        <Box sx={{ minWidth: 0, flex: 1, overflow: 'visible' }}>
          <Typography
            variant="subtitle2"
            title={person.name}
            sx={{
              fontWeight: nameWeight,
              lineHeight: 1.25,
              fontSize: nameSize,
              letterSpacing: '-0.01em',
              color: orgTokens.ink[900],
              wordBreak: 'break-word',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {person.name}
          </Typography>
          <Typography
            variant="caption"
            title={title}
            sx={{
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              lineHeight: 1.35,
              mt: 0.25,
              fontSize: tier === 'root' ? 12.5 : 11.5,
              fontWeight: 400,
              letterSpacing: tier === 'root' ? '0.04em' : 0,
              textTransform: tier === 'root' ? 'uppercase' : 'none',
              color: orgTokens.ink[600],
            }}
          >
            {title}
          </Typography>
          {(stampLabel || person.stream_name) && (
            <Stack direction="row" spacing={0.75} useFlexGap sx={{ mt: 0.85, flexWrap: 'wrap', alignItems: 'center' }}>
              {stampLabel ? <RankStamp label={stampLabel} accent={inkAccent} /> : null}
              {person.stream_name && !stampLabel ? (
                <Typography
                  variant="caption"
                  sx={{ color: orgTokens.ink[400], fontSize: 11, fontWeight: 500 }}
                >
                  {person.stream_name}
                </Typography>
              ) : person.stream_name && stampLabel ? (
                <Typography
                  variant="caption"
                  sx={{ color: orgTokens.ink[400], fontSize: 11, fontWeight: 500 }}
                >
                  · {person.stream_name}
                </Typography>
              ) : null}
            </Stack>
          )}
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
        event.stopPropagation();
        event.dataTransfer.dropEffect = 'move';
        setDropTargetId(team.team_id);
      }}
      onDragLeave={() => {
        if (dropTargetId === team.team_id) setDropTargetId(null);
      }}
      onDrop={(event) => {
        if (!canEdit) return;
        event.preventDefault();
        event.stopPropagation();
        setDropTargetId(null);
        onDropPerson(team);
      }}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        width: '100%',
        p: 1.75,
        pl: 2,
        borderRadius: `${orgTokens.radius.bay}px`,
        border: '1px solid',
        borderColor: isOver ? alpha(line, 0.55) : orgTokens.border.hair,
        borderLeft: `2px solid ${isOver ? line : alpha(line, 0.7)}`,
        bgcolor: isOver ? alpha(line, 0.06) : alpha(line, 0.025),
        boxShadow: isOver ? `inset 0 0 0 3px ${alpha(line, 0.08)}` : 'none',
        transition: `border-color ${orgTokens.motion}, box-shadow ${orgTokens.motion}, background-color ${orgTokens.motion}`,
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1.5 }}>
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: line,
            flexShrink: 0,
            boxShadow: `0 0 0 3px ${alpha(line, 0.12)}`,
          }}
        />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 700, color: orgTokens.ink[900], letterSpacing: '-0.01em' }}
            noWrap
          >
            {team.team_name}
          </Typography>
          <Typography variant="caption" sx={{ color: orgTokens.ink[400] }} noWrap>
            {team.team_lead_name ? `Lead · ${team.team_lead_name}` : 'No team lead'}
            {canEdit ? ' · drop cards here' : ''}
          </Typography>
        </Box>
        <CountBadge label={String(team.member_count)} />
      </Stack>

      {forest.length === 0 ? (
        <Typography
          variant="caption"
          sx={{
            py: 2.5,
            border: '1px dashed',
            borderColor: alpha(line, 0.35),
            borderRadius: `${orgTokens.radius.bay}px`,
            textAlign: 'center',
            color: orgTokens.ink[400],
            bgcolor: alpha(line, 0.03),
          }}
        >
          {canEdit ? 'Drop a person card onto this team' : 'No members'}
        </Typography>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fill, ${orgTokens.card.w}px)`,
            justifyContent: 'start',
            gap: orgTokens.gap.card,
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
  onDropToDepartment,
}: {
  department: OrgChartDepartment;
  canEdit: boolean;
  dropTargetId: string | null;
  setDropTargetId: (id: string | null) => void;
  onPersonDragStart: (person: OrgChartPerson) => void;
  onDropPerson: (target: OrgChartTeamColumn) => void;
  onDropToDepartment: (department: OrgChartDepartment) => void;
}) {
  const accent = department.colour;
  const isDeptOver = dropTargetId === department.department_id;
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
      onDragOver={(event) => {
        if (!canEdit) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        setDropTargetId(department.department_id);
      }}
      onDragLeave={() => {
        if (dropTargetId === department.department_id) setDropTargetId(null);
      }}
      onDrop={(event) => {
        if (!canEdit) return;
        event.preventDefault();
        setDropTargetId(null);
        onDropToDepartment(department);
      }}
      sx={{
        position: 'relative',
        borderRadius: `${orgTokens.radius.plate}px`,
        border: '1px solid',
        borderColor: isDeptOver ? alpha(accent, 0.45) : orgTokens.border.hair,
        overflow: 'hidden',
        bgcolor: isDeptOver ? alpha(accent, 0.04) : orgTokens.ink.paper,
        boxShadow: isDeptOver ? `0 0 0 2px ${alpha(accent, 0.2)}` : 'none',
        transition: `border-color ${orgTokens.motion}, box-shadow ${orgTokens.motion}, background-color ${orgTokens.motion}`,
        '&::before': {
          content: '""',
          position: 'absolute',
          left: 0,
          right: 0,
          top: 0,
          height: 3,
          bgcolor: accent,
          zIndex: 1,
        },
      }}
    >
      <Box
        sx={{
          px: { xs: 2, md: 2.75 },
          py: 1.75,
          borderBottom: '1px solid',
          borderColor: orgTokens.border.hair,
          bgcolor: alpha(orgTokens.ink.paper, 0.96),
          position: 'sticky',
          top: 0,
          zIndex: 2,
          backdropFilter: 'blur(8px)',
        }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <Stack direction="row" spacing={1.25} sx={{ alignItems: 'flex-start', minWidth: 0 }}>
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: '3px',
                bgcolor: accent,
                mt: 0.85,
                flexShrink: 0,
              }}
            />
            <Box sx={{ minWidth: 0 }}>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 700,
                  color: orgTokens.ink[900],
                  lineHeight: 1.25,
                  letterSpacing: '-0.015em',
                  fontSize: { xs: 17, md: 18 },
                }}
              >
                {department.name}
              </Typography>
              <Typography variant="body2" sx={{ mt: 0.35, color: orgTokens.ink[600] }}>
                {isEmpty
                  ? department.description || 'Reserved for future expansion'
                  : department.head_name
                    ? `Head · ${department.head_name}${department.head_title ? ` · ${department.head_title}` : ''}`
                    : department.description || `${department.member_count} people`}
              </Typography>
            </Box>
          </Stack>
          <Box sx={{ alignSelf: { xs: 'flex-start', sm: 'center' }, pl: { xs: 2.75, sm: 0 } }}>
            <CountBadge label={isEmpty ? 'Future' : `${department.member_count} people`} />
          </Box>
        </Stack>
      </Box>

      <Box sx={{ px: { xs: 2, md: 2.75 }, py: 2.5 }}>
        {isEmpty ? (
          <Box
            sx={{
              py: 3,
              px: 2,
              borderRadius: `${orgTokens.radius.bay}px`,
              border: '1px solid',
              borderColor: alpha(accent, 0.2),
              textAlign: 'center',
              color: orgTokens.ink[600],
              background: `repeating-linear-gradient(45deg, ${alpha(accent, 0.05)} 0 6px, transparent 6px 12px)`,
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 600, color: orgTokens.ink[900] }}>
              No people assigned yet
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: orgTokens.ink[400] }}>
              This department is ready for future org growth.
            </Typography>
          </Box>
        ) : (
          <Stack spacing={orgTokens.gap.section}>
            {head ? (
              <Box>
                <SectionEyebrow label="Department head" />
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 0.5 }}>
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
                <SectionEyebrow
                  label={department.code === 'engineering' ? 'Leadership & HQ' : 'Department staff'}
                />
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(auto-fill, ${orgTokens.card.w}px)`,
                    justifyContent: 'start',
                    gap: orgTokens.gap.card,
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
                <SectionEyebrow label="Delivery teams" />
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: {
                      xs: '1fr',
                      lg: 'repeat(2, minmax(0, 1fr))',
                    },
                    gap: orgTokens.gap.team,
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

  const assignDeptMutation = useMutation({
    mutationFn: async (vars: { person: OrgChartPerson; department: OrgChartDepartment }) =>
      orgDepartmentsApi.assignUser(vars.department.department_id, vars.person.user_id),
    onSuccess: async (_data, vars) => {
      showSuccess(`${vars.person.name} moved to ${vars.department.name}.`);
      setDragPerson(null);
      await queryClient.invalidateQueries({ queryKey: ORG_CHART_KEY });
      await queryClient.invalidateQueries({ queryKey: ['org-departments'] });
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const handleDropOnDepartment = useCallback(
    (department: OrgChartDepartment) => {
      if (!dragPerson) return;
      const person = dragPerson;
      setDragPerson(null);
      if (person.org_department_id === department.department_id) return;
      assignDeptMutation.mutate({ person, department });
    },
    [dragPerson, assignDeptMutation],
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

  const companyRoot = useMemo(() => {
    const root = chartQuery.data?.company_root ?? null;
    if (!root || shouldHidePerson(root, viewPrefs)) return null;
    return root;
  }, [chartQuery.data?.company_root, viewPrefs]);

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
  const totalTeams = filteredDepartments.reduce((sum, row) => sum + row.teams.length, 0);
  const hiddenCount =
    viewPrefs.hidePlanningBoard || viewPrefs.hideSystemAdmin
      ? 'Service accounts can be shown via View options'
      : null;

  const setPref = (key: keyof ViewPrefs, value: boolean) => {
    setViewPrefs((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Box
      sx={{
        mx: { xs: -1, md: -1.5 },
        px: { xs: 1, md: 1.5 },
        pb: 3,
        background: `
          linear-gradient(${orgTokens.ink.canvas}, ${orgTokens.ink.canvas}),
          repeating-linear-gradient(
            0deg,
            transparent,
            transparent 23px,
            rgba(31,43,56,0.022) 23px,
            rgba(31,43,56,0.022) 24px
          ),
          repeating-linear-gradient(
            90deg,
            transparent,
            transparent 23px,
            rgba(31,43,56,0.022) 23px,
            rgba(31,43,56,0.022) 24px
          )
        `,
        backgroundBlendMode: 'normal, multiply, multiply',
        minHeight: '70vh',
        borderRadius: 2,
      }}
    >
      <PageHeader
        subtitle="Company structure as a classic organisation chart — departments, heads, and delivery teams."
        action={
          <Tooltip title="Refresh chart">
            <span>
              <IconButton
                onClick={() => void chartQuery.refetch()}
                disabled={chartQuery.isFetching}
                size="small"
                sx={{
                  border: '1px solid',
                  borderColor: orgTokens.border.mid,
                  borderRadius: `${orgTokens.radius.bay}px`,
                  bgcolor: orgTokens.ink.paper,
                }}
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        }
      />

      <Box
        sx={{
          mb: 2,
          pb: 2,
          borderBottom: '1px solid',
          borderColor: orgTokens.border.hair,
        }}
      >
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1.5}
          sx={{ alignItems: { md: 'flex-end' }, justifyContent: 'space-between' }}
        >
          <Box>
            <Typography
              variant="h5"
              sx={{
                fontWeight: 700,
                letterSpacing: '-0.02em',
                color: orgTokens.ink[900],
                fontSize: { xs: 22, md: 26 },
              }}
            >
              Organization Chart
            </Typography>
            <Typography
              variant="body2"
              sx={{ mt: 0.75, maxWidth: 720, color: orgTokens.ink[600], lineHeight: 1.5 }}
            >
              {chartQuery.data?.note ??
                (canEdit
                  ? 'Drop a card on a delivery team, confirm the effective date, then save.'
                  : 'View limited to your division or teams you lead.')}
            </Typography>
          </Box>
          {hasDepartmentView ? (
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: orgTokens.ink[400],
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
                pb: 0.25,
              }}
            >
              {filteredDepartments.length} departments · {totalPeople} people · {totalTeams} teams
            </Typography>
          ) : null}
        </Stack>
      </Box>

      <Box
        sx={{
          mb: 3,
          px: 1.75,
          py: 1.25,
          borderRadius: `${orgTokens.radius.bay}px`,
          border: '1px solid',
          borderColor: orgTokens.border.hair,
          bgcolor: alpha(orgTokens.ink.paper, 0.94),
          backdropFilter: 'blur(8px)',
          boxShadow: '0 1px 2px rgba(31,43,56,.04)',
          position: 'sticky',
          top: 8,
          zIndex: 4,
        }}
      >
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between', mb: 0.25 }}
        >
          <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
            <VisibilityOffRoundedIcon sx={{ fontSize: 17, color: orgTokens.ink[400] }} />
            <Typography
              variant="subtitle2"
              sx={{ fontWeight: 700, color: orgTokens.ink[900], letterSpacing: '-0.01em' }}
            >
              View options
            </Typography>
            {canEdit ? (
              <Chip
                size="small"
                icon={<DragIndicatorIcon sx={{ fontSize: '14px !important' }} />}
                label="Drag to reassign"
                sx={{
                  height: 24,
                  ml: 0.5,
                  bgcolor: alpha(theme.palette.primary.main, 0.06),
                  border: '1px solid',
                  borderColor: orgTokens.border.mid,
                  color: orgTokens.ink[600],
                  '& .MuiChip-label': { px: 0.75, fontSize: 11, fontWeight: 600 },
                  '& .MuiChip-icon': { color: orgTokens.ink[400] },
                }}
              />
            ) : null}
          </Stack>
          {hiddenCount ? (
            <Typography variant="caption" sx={{ color: orgTokens.ink[400] }}>
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
            label={<Typography variant="body2">Hide Planning Board</Typography>}
          />
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={viewPrefs.hideSystemAdmin}
                onChange={(event) => setPref('hideSystemAdmin', event.target.checked)}
              />
            }
            label={<Typography variant="body2">Hide System Admin</Typography>}
          />
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={viewPrefs.hideEmptyDepartments}
                onChange={(event) => setPref('hideEmptyDepartments', event.target.checked)}
              />
            }
            label={<Typography variant="body2">Hide empty departments</Typography>}
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
        <Box
          sx={{
            position: 'relative',
            pl: { xl: `${28}px` },
            '&::before': {
              content: '""',
              display: { xs: 'none', xl: 'block' },
              position: 'absolute',
              left: 6,
              top: companyRoot ? 120 : 12,
              bottom: 40,
              width: '1.5px',
              bgcolor: orgTokens.connector.ink,
              maskImage: 'linear-gradient(to bottom, #000 0%, #000 85%, transparent 100%)',
            },
          }}
        >
          <Stack spacing={orgTokens.gap.dept}>
            {hasDepartmentView && companyRoot ? (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  pt: 0.5,
                  pb: 0.5,
                }}
              >
                <Stack
                  direction="row"
                  spacing={1.5}
                  sx={{ alignItems: 'center', mb: 1.5, width: '100%', maxWidth: 420 }}
                >
                  <Box sx={{ flex: 1, height: '1px', bgcolor: orgTokens.border.mid }} />
                  <Typography
                    variant="overline"
                    sx={{
                      letterSpacing: '0.12em',
                      color: orgTokens.ink[400],
                      fontWeight: 700,
                      flexShrink: 0,
                    }}
                  >
                    Organization Head
                  </Typography>
                  <Box sx={{ flex: 1, height: '1px', bgcolor: orgTokens.border.mid }} />
                </Stack>
                <PersonCard
                  person={companyRoot}
                  accent="#455a64"
                  canEdit={canEdit}
                  onDragStart={setDragPerson}
                  featured
                  executive
                />
                <Box
                  sx={{
                    width: orgTokens.connector.width,
                    height: orgTokens.connector.execSpine,
                    bgcolor: orgTokens.connector.ink,
                    mt: 1.25,
                  }}
                />
              </Box>
            ) : null}
            {hasDepartmentView ? (
              filteredDepartments.map((department) => (
                <Box
                  key={department.department_id}
                  sx={{
                    position: 'relative',
                    '&::before': {
                      content: '""',
                      display: { xs: 'none', xl: 'block' },
                      position: 'absolute',
                      left: -22,
                      top: 28,
                      width: 14,
                      height: '1.5px',
                      bgcolor: orgTokens.connector.ink,
                    },
                  }}
                >
                  <DepartmentSection
                    department={department}
                    canEdit={canEdit}
                    dropTargetId={dropTargetId}
                    setDropTargetId={setDropTargetId}
                    onPersonDragStart={setDragPerson}
                    onDropPerson={handleDropOnTeam}
                    onDropToDepartment={handleDropOnDepartment}
                  />
                </Box>
              ))
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    md: 'repeat(auto-fit, minmax(280px, 1fr))',
                  },
                  gap: 2,
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
                  borderRadius: `${orgTokens.radius.plate}px`,
                  border: '1px dashed',
                  borderColor: alpha(theme.palette.warning.main, 0.4),
                  p: 2.25,
                  bgcolor: alpha(theme.palette.warning.main, 0.04),
                  backgroundImage: `repeating-linear-gradient(45deg, ${alpha(
                    theme.palette.warning.main,
                    0.04,
                  )} 0 6px, transparent 6px 12px)`,
                }}
              >
                <SectionEyebrow label="Unassigned" />
                <Typography
                  variant="caption"
                  sx={{ display: 'block', mb: 1.75, color: orgTokens.ink[400], mt: -0.5 }}
                >
                  Drag onto a delivery team to set primary home
                </Typography>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: `repeat(auto-fill, ${orgTokens.card.w}px)`,
                    justifyContent: 'start',
                    gap: orgTokens.gap.card,
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
        </Box>
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
