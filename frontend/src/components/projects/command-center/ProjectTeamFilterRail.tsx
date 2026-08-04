import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import { Box, ButtonBase, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

export interface ProjectTeamFilterOption {
  id: string;
  label: string;
  count: number;
}

interface ProjectTeamFilterRailProps {
  options: ProjectTeamFilterOption[];
  /** Empty selection = all teams. */
  selectedIds: string[];
  onChange: (nextIds: string[]) => void;
}

export function ProjectTeamFilterRail({
  options,
  selectedIds,
  onChange,
}: ProjectTeamFilterRailProps) {
  if (!options.length) return null;

  const allSelected = selectedIds.length === 0;
  const selectedSet = new Set(selectedIds);
  const total = options.reduce((sum, option) => sum + option.count, 0);

  const selectAll = () => onChange([]);

  const toggleTeam = (teamId: string) => {
    if (allSelected) {
      onChange([teamId]);
      return;
    }
    if (selectedSet.has(teamId)) {
      const next = selectedIds.filter((id) => id !== teamId);
      onChange(next.length === 0 || next.length === options.length ? [] : next);
      return;
    }
    const next = [...selectedIds, teamId];
    onChange(next.length >= options.length ? [] : next);
  };

  return (
    <Box
      sx={{
        width: { xs: '100%', lg: 220 },
        flexShrink: 0,
        position: { lg: 'sticky' },
        top: { lg: 88 },
        alignSelf: 'flex-start',
      }}
    >
      <Typography
        variant="caption"
        sx={{
          display: 'block',
          mb: 0.75,
          fontWeight: 700,
          color: 'text.secondary',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        Teams
      </Typography>

      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'row', lg: 'column' },
          gap: 0.75,
          overflowX: { xs: 'auto', lg: 'visible' },
          pb: { xs: 0.5, lg: 0 },
        }}
      >
        <ButtonBase
          aria-pressed={allSelected}
          onClick={selectAll}
          sx={{
            minWidth: { xs: 140, lg: 'auto' },
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
            px: 1.1,
            py: 0.9,
            borderRadius: `${designTokens.radius.md}px`,
            border: '1px solid',
            borderColor: allSelected ? designTokens.semantic.primary : 'divider',
            bgcolor: allSelected ? designTokens.semantic.primarySoft : designTokens.semantic.card,
            boxShadow: designTokens.elevation.card,
            textAlign: 'left',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <GroupsOutlinedIcon sx={{ fontSize: 16, color: designTokens.semantic.primary }} />
            <Typography variant="caption" sx={{ fontWeight: 700 }}>
              All teams
            </Typography>
          </Box>
          <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
            {total}
          </Typography>
        </ButtonBase>

        {options.map((option) => {
          const selected = !allSelected && selectedSet.has(option.id);
          return (
            <ButtonBase
              key={option.id}
              aria-pressed={selected}
              onClick={() => toggleTeam(option.id)}
              sx={{
                minWidth: { xs: 160, lg: 'auto' },
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 1,
                px: 1.1,
                py: 0.9,
                borderRadius: `${designTokens.radius.md}px`,
                border: '1px solid',
                borderColor: selected ? designTokens.semantic.primary : 'divider',
                bgcolor: selected ? designTokens.semantic.primarySoft : designTokens.semantic.card,
                boxShadow: selected ? 'none' : designTokens.elevation.card,
                textAlign: 'left',
                '&:hover': {
                  borderColor: designTokens.semantic.primary,
                  bgcolor: selected
                    ? designTokens.semantic.primarySoft
                    : designTokens.semantic.neutralSoft,
                },
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  fontWeight: selected ? 700 : 600,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  textAlign: 'left',
                }}
              >
                {option.label}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 700,
                  color: selected ? designTokens.semantic.primary : 'text.secondary',
                  flexShrink: 0,
                }}
              >
                {option.count}
              </Typography>
            </ButtonBase>
          );
        })}
      </Box>
    </Box>
  );
}
