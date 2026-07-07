import { useMemo } from 'react';
import {
  Box,
  Chip,
  List,
  ListItemButton,
  ListItemText,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import type { ResourcePlanningDesignerRow } from '../../types/ResourcePlanning';
import type { TeamResourcePlanningRow } from '../../types/Team';
import type { Department } from '../../types/Settings';
import { EntityAvatar, UtilizationBar } from '../ui/design-system';
import { designTokens } from '../../theme/designTokens';
import { formatNumber } from '../../utils/format';

type LeftPanelTab = 'designers' | 'teams' | 'departments';

interface ResourcePlanningLeftPanelProps {
  tab: LeftPanelTab;
  onTabChange: (tab: LeftPanelTab) => void;
  designers: ResourcePlanningDesignerRow[];
  teams: TeamResourcePlanningRow[];
  departments: Department[];
  selectedDesignerId: string | null;
  selectedTeamId: string | null;
  onSelectDesigner: (id: string | null) => void;
  onSelectTeam: (id: string | null) => void;
}

function designerUtilization(designer: ResourcePlanningDesignerRow): number {
  if (designer.capacity_hours <= 0) return 0;
  return Math.round((designer.allocated_hours / designer.capacity_hours) * 100);
}

export function ResourcePlanningLeftPanel({
  tab,
  onTabChange,
  designers,
  teams,
  departments,
  selectedDesignerId,
  selectedTeamId,
  onSelectDesigner,
  onSelectTeam,
}: ResourcePlanningLeftPanelProps) {
  const sortedDesigners = useMemo(
    () => [...designers].sort((a, b) => designerUtilization(b) - designerUtilization(a)),
    [designers],
  );

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid',
        borderColor: 'divider',
        bgcolor: designTokens.semantic.card,
        borderRadius: `${designTokens.radius.lg}px`,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ px: 1.5, pt: 1 }}>
        <Tabs
          value={tab}
          onChange={(_, value: LeftPanelTab) => onTabChange(value)}
          variant="fullWidth"
          sx={{ minHeight: 40 }}
        >
          <Tab label="Designers" value="designers" sx={{ minHeight: 40, fontSize: '0.7rem' }} />
          <Tab label="Teams" value="teams" sx={{ minHeight: 40, fontSize: '0.7rem' }} />
          <Tab label="Depts" value="departments" sx={{ minHeight: 40, fontSize: '0.7rem' }} />
        </Tabs>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', px: 1.5, pb: 1.5 }}>
        {tab === 'designers' ? (
          <List dense disablePadding>
            {sortedDesigners.map((designer) => {
              const util = designerUtilization(designer);
              const isLeave = designer.availability_status.toLowerCase().includes('leave');
              return (
                <ListItemButton
                  key={designer.user_id}
                  selected={selectedDesignerId === designer.user_id}
                  onClick={() =>
                    onSelectDesigner(
                      selectedDesignerId === designer.user_id ? null : designer.user_id,
                    )
                  }
                  sx={{ borderRadius: `${designTokens.radius.sm}px`, mb: 0.5, alignItems: 'flex-start' }}
                >
                  <Box sx={{ width: '100%' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
                      <EntityAvatar label={designer.designer_name} size={28} />
                      <ListItemText
                        primary={designer.designer_name}
                        secondary={designer.team_name ?? 'Unassigned'}
                        slotProps={{
                          primary: { sx: { fontWeight: 700, fontSize: '0.8125rem' } },
                          secondary: { sx: { fontSize: '0.7rem' } },
                        }}
                      />
                      {isLeave ? (
                        <Chip label="Leave" size="small" sx={{ height: 20, bgcolor: designTokens.semantic.neutralSoft }} />
                      ) : null}
                    </Box>
                    <UtilizationBar label="" value={util} showValue />
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      {formatNumber(designer.allocated_hours)}h / {formatNumber(designer.capacity_hours)}h
                    </Typography>
                  </Box>
                </ListItemButton>
              );
            })}
          </List>
        ) : null}

        {tab === 'teams' ? (
          <List dense disablePadding>
            {teams.map((team) => (
              <ListItemButton
                key={team.team_id}
                selected={selectedTeamId === team.team_id}
                onClick={() =>
                  onSelectTeam(selectedTeamId === team.team_id ? null : team.team_id)
                }
                sx={{ borderRadius: `${designTokens.radius.sm}px`, mb: 0.5 }}
              >
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    bgcolor: team.team_colour,
                    mr: 1,
                    flexShrink: 0,
                  }}
                />
                <ListItemText
                  primary={team.team_name}
                  secondary={`${team.member_count} members · ${formatNumber(team.utilization_percent)}% util`}
                  slotProps={{ primary: { sx: { fontWeight: 700, fontSize: '0.8125rem' } } }}
                />
              </ListItemButton>
            ))}
          </List>
        ) : null}

        {tab === 'departments' ? (
          <List dense disablePadding>
            {departments.map((dept) => (
              <ListItemButton key={dept.id} disabled sx={{ borderRadius: `${designTokens.radius.sm}px`, mb: 0.5, opacity: 0.85 }}>
                <ListItemText
                  primary={dept.name}
                  secondary={dept.code ?? 'Organisation unit'}
                  slotProps={{ primary: { sx: { fontWeight: 600, fontSize: '0.8125rem' } } }}
                />
              </ListItemButton>
            ))}
            {!departments.length ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
                No departments configured.
              </Typography>
            ) : null}
          </List>
        ) : null}
      </Box>
    </Box>
  );
}

export type { LeftPanelTab };
