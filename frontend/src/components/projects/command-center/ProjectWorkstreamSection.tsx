import { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PushPinIcon from '@mui/icons-material/PushPin';
import PushPinOutlinedIcon from '@mui/icons-material/PushPinOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import ArchitectureIcon from '@mui/icons-material/Architecture';
import BuildOutlinedIcon from '@mui/icons-material/BuildOutlined';
import ChangeCircleOutlinedIcon from '@mui/icons-material/ChangeCircleOutlined';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import PrecisionManufacturingOutlinedIcon from '@mui/icons-material/PrecisionManufacturingOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import VerifiedOutlinedIcon from '@mui/icons-material/VerifiedOutlined';
import type { Customer, Project, Stream, Team, User } from '../../../types';
import type { ProjectTableRow } from '../ProjectTable';
import { ProjectBoardList } from './ProjectBoardList';
import type { WorkstreamProjectGroup } from '../../../utils/projectWorkstreamGroups';
import { designTokens } from '../../../theme/designTokens';
import { formatNumber } from '../../../utils/format';

/** Map catalog icon keys → MUI icons. Keys come from workstream.icon config. */
const ICON_BY_KEY: Record<string, typeof AccountTreeOutlinedIcon> = {
  precision: PrecisionManufacturingOutlinedIcon,
  build: BuildOutlinedIcon,
  architecture: ArchitectureIcon,
  change: ChangeCircleOutlinedIcon,
  science: ScienceOutlinedIcon,
  lightbulb: LightbulbOutlinedIcon,
  verified: VerifiedOutlinedIcon,
  tree: AccountTreeOutlinedIcon,
};

function iconFor(key: string | null | undefined) {
  if (!key) return AccountTreeOutlinedIcon;
  return ICON_BY_KEY[key.toLowerCase()] ?? AccountTreeOutlinedIcon;
}

interface ProjectWorkstreamSectionProps {
  group: WorkstreamProjectGroup;
  customers: Customer[];
  users: User[];
  streams: Stream[];
  teams: Team[];
  pinned?: boolean;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  onTogglePin?: (workstreamId: string) => void;
  gridSessionKey?: number;
  onRowOpen?: (row: ProjectTableRow) => void;
  onEdit?: (row: ProjectTableRow) => void;
  onArchive?: (projectId: string) => void;
  onDuplicate?: (projectId: string) => void;
  onExport?: (row: ProjectTableRow) => void;
  onDelete?: (projectId: string) => void;
  canDelete?: boolean;
}

function SummaryStat({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <Box sx={{ minWidth: 64 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.2 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{
          fontWeight: 700,
          lineHeight: 1.3,
          color: emphasize ? 'error.main' : 'text.primary',
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}

export function ProjectWorkstreamSection({
  group,
  customers,
  users,
  streams,
  teams,
  pinned = false,
  collapsed,
  onCollapsedChange,
  onTogglePin,
  gridSessionKey: _gridSessionKey,
  onRowOpen,
  onEdit,
  onArchive,
  onDuplicate,
  onExport,
  onDelete,
  canDelete,
}: ProjectWorkstreamSectionProps) {
  const [expanded, setExpanded] = useState(() => collapsed !== true);

  useEffect(() => {
    if (collapsed !== undefined) {
      setExpanded(!collapsed);
    }
  }, [collapsed]);

  const handleExpand = (_: unknown, next: boolean) => {
    setExpanded(next);
    onCollapsedChange?.(!next);
  };

  const accent = group.color || designTokens.semantic.primary;
  const Icon = iconFor(group.icon);
  const { summary } = group;

  return (
    <Accordion
      expanded={expanded}
      onChange={handleExpand}
      disableGutters
      elevation={0}
      sx={{
        mb: 1.25,
        width: '100%',
        border: '1px solid',
        borderColor: 'divider',
        borderLeft: `4px solid ${accent}`,
        borderRadius: `${designTokens.radius.md}px !important`,
        bgcolor: designTokens.semantic.card,
        boxShadow: designTokens.elevation.card,
        '&:before': { display: 'none' },
        overflow: 'hidden',
        '& .MuiCollapse-root': { width: '100%' },
        '& .MuiCollapse-wrapper': { width: '100%' },
        '& .MuiCollapse-wrapperInner': { width: '100%' },
        '& .MuiAccordionDetails-root': {
          width: '100%',
          boxSizing: 'border-box',
        },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{
          minHeight: 56,
          px: 1.5,
          width: '100%',
          '& .MuiAccordionSummary-content': {
            my: 1,
            flexDirection: 'column',
            alignItems: 'stretch',
            gap: 0.75,
            width: '100%',
            marginRight: 1,
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          <Icon sx={{ fontSize: 20, color: accent, flexShrink: 0 }} />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, lineHeight: 1.25 }}>
              {group.label.toUpperCase()}
              <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1, fontWeight: 600 }}>
                ({summary.activeCount})
              </Typography>
              {pinned ? (
                <Typography component="span" variant="caption" color="primary" sx={{ ml: 1, fontWeight: 700 }}>
                  Pinned
                </Typography>
              ) : null}
            </Typography>
            {group.description ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {group.description}
              </Typography>
            ) : null}
          </Box>
          <Box
            sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}
            onClick={(event) => event.stopPropagation()}
          >
            {onTogglePin ? (
              <Tooltip title={pinned ? 'Unpin section' : 'Pin favourite section'}>
                <IconButton
                  size="small"
                  aria-label={pinned ? 'Unpin section' : 'Pin section'}
                  onClick={() => onTogglePin(group.id)}
                >
                  {pinned ? (
                    <PushPinIcon fontSize="small" color="primary" />
                  ) : (
                    <PushPinOutlinedIcon fontSize="small" />
                  )}
                </IconButton>
              </Tooltip>
            ) : null}
          </Box>
        </Box>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: { xs: 1.25, sm: 1.75 },
            pl: { xs: 0, sm: 3.5 },
          }}
          onClick={(event) => event.stopPropagation()}
        >
          <SummaryStat label="Projects" value={String(summary.activeCount)} />
          <SummaryStat label="Hours" value={formatNumber(summary.actualHours, 0)} />
          <SummaryStat label="Progress" value={`${formatNumber(summary.completionPercent, 0)}%`} />
          <SummaryStat label="Risk" value={String(summary.riskCount)} emphasize={summary.riskCount > 0} />
          <SummaryStat label="Due soon" value={String(summary.dueSoonCount)} />
          <SummaryStat
            label="Overdue"
            value={String(summary.overdueCount)}
            emphasize={summary.overdueCount > 0}
          />
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 1.25, pt: 0, width: '100%' }}>
        {group.projects.length ? (
          <ProjectBoardList
            projects={group.projects as Project[]}
            customers={customers}
            users={users}
            streams={streams}
            teams={teams}
            splitActiveHold
            onRowOpen={onRowOpen}
            onEdit={onEdit}
            onArchive={onArchive}
            onDuplicate={onDuplicate}
            onExport={onExport}
            onDelete={onDelete}
            canDelete={canDelete}
          />
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ px: 1, py: 1.5 }}>
            No projects in this workstream for the current filters.
          </Typography>
        )}
      </AccordionDetails>
    </Accordion>
  );
}
