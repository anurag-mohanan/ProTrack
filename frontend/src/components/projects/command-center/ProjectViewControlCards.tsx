import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import { Box, ButtonBase, FormControlLabel, Switch, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

export interface ViewControlOption {
  id: string;
  label: string;
  count?: number;
}

interface MultiSelectCardsProps {
  title: string;
  icon: typeof AccountTreeOutlinedIcon;
  options: ViewControlOption[];
  selectedIds: string[];
  onChange: (nextIds: string[]) => void;
  accent?: string;
}

function MultiSelectCards({
  title,
  icon: Icon,
  options,
  selectedIds,
  onChange,
  accent = designTokens.semantic.primary,
}: MultiSelectCardsProps) {
  if (!options.length) return null;
  const allSelected = selectedIds.length === 0;
  const selectedSet = new Set(selectedIds);

  const toggle = (id: string) => {
    if (allSelected) {
      onChange([id]);
      return;
    }
    if (selectedSet.has(id)) {
      const next = selectedIds.filter((x) => x !== id);
      onChange(next.length === 0 || next.length === options.length ? [] : next);
      return;
    }
    const next = [...selectedIds, id];
    onChange(next.length >= options.length ? [] : next);
  };

  return (
    <Box sx={{ mb: 1.25 }}>
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
        {title}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'row', md: 'row' },
          flexWrap: 'wrap',
          gap: 0.75,
          overflowX: { xs: 'auto', md: 'visible' },
          pb: { xs: 0.5, md: 0 },
        }}
      >
        <ButtonBase
          aria-pressed={allSelected}
          onClick={() => onChange([])}
          sx={{
            minWidth: 120,
            px: 1.1,
            py: 0.9,
            borderRadius: `${designTokens.radius.md}px`,
            border: '1px solid',
            borderColor: allSelected ? accent : 'divider',
            bgcolor: allSelected ? `${accent}14` : designTokens.semantic.card,
            boxShadow: designTokens.elevation.card,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Icon sx={{ fontSize: 16, color: accent }} />
            <Typography variant="caption" sx={{ fontWeight: 700 }}>
              All
            </Typography>
          </Box>
        </ButtonBase>
        {options.map((option) => {
          const selected = !allSelected && selectedSet.has(option.id);
          return (
            <ButtonBase
              key={option.id}
              aria-pressed={selected}
              onClick={() => toggle(option.id)}
              sx={{
                minWidth: 120,
                px: 1.1,
                py: 0.9,
                borderRadius: `${designTokens.radius.md}px`,
                border: '1px solid',
                borderColor: selected ? accent : 'divider',
                bgcolor: selected ? `${accent}14` : designTokens.semantic.card,
                boxShadow: designTokens.elevation.card,
                textAlign: 'left',
                '&:hover': { borderColor: accent },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, width: '100%' }}>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>
                  {option.label}
                </Typography>
                {typeof option.count === 'number' ? (
                  <Typography variant="caption" color="text.secondary">
                    {option.count}
                  </Typography>
                ) : null}
              </Box>
            </ButtonBase>
          );
        })}
      </Box>
    </Box>
  );
}

interface ProjectViewControlCardsProps {
  workstreams: ViewControlOption[];
  teams: ViewControlOption[];
  statusBuckets: ViewControlOption[];
  selectedWorkstreamIds: string[];
  selectedTeamIds: string[];
  selectedStatusIds: string[];
  onWorkstreamsChange: (ids: string[]) => void;
  onTeamsChange: (ids: string[]) => void;
  onStatusChange: (ids: string[]) => void;
  showWorkstreams: boolean;
  showTeams: boolean;
  showStatus: boolean;
  onShowWorkstreamsChange: (value: boolean) => void;
  onShowTeamsChange: (value: boolean) => void;
  onShowStatusChange: (value: boolean) => void;
}

export function ProjectViewControlCards({
  workstreams,
  teams,
  statusBuckets,
  selectedWorkstreamIds,
  selectedTeamIds,
  selectedStatusIds,
  onWorkstreamsChange,
  onTeamsChange,
  onStatusChange,
  showWorkstreams,
  showTeams,
  showStatus,
  onShowWorkstreamsChange,
  onShowTeamsChange,
  onShowStatusChange,
}: ProjectViewControlCardsProps) {
  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mb: 1 }}>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={showWorkstreams}
              onChange={(e) => onShowWorkstreamsChange(e.target.checked)}
            />
          }
          label={<Typography variant="caption">Show Workstreams</Typography>}
        />
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={showTeams}
              onChange={(e) => onShowTeamsChange(e.target.checked)}
            />
          }
          label={<Typography variant="caption">Show Teams</Typography>}
        />
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={showStatus}
              onChange={(e) => onShowStatusChange(e.target.checked)}
            />
          }
          label={<Typography variant="caption">Show Status</Typography>}
        />
      </Box>
      {showWorkstreams ? (
        <MultiSelectCards
          title="Workstreams"
          icon={AccountTreeOutlinedIcon}
          options={workstreams}
          selectedIds={selectedWorkstreamIds}
          onChange={onWorkstreamsChange}
          accent="#0d9488"
        />
      ) : null}
      {showTeams ? (
        <MultiSelectCards
          title="Teams"
          icon={GroupsOutlinedIcon}
          options={teams}
          selectedIds={selectedTeamIds}
          onChange={onTeamsChange}
        />
      ) : null}
      {showStatus ? (
        <MultiSelectCards
          title="Status"
          icon={FlagOutlinedIcon}
          options={statusBuckets}
          selectedIds={selectedStatusIds}
          onChange={onStatusChange}
          accent="#c2410c"
        />
      ) : null}
    </Box>
  );
}
