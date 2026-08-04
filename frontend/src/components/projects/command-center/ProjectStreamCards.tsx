import ArchitectureIcon from '@mui/icons-material/Architecture';
import PrecisionManufacturingOutlinedIcon from '@mui/icons-material/PrecisionManufacturingOutlined';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import { Box, ButtonBase, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

export interface ProjectStreamCardOption {
  id: string;
  label: string;
  activeCount: number;
  pastCount: number;
}

interface ProjectStreamCardsProps {
  options: ProjectStreamCardOption[];
  /** Empty selection = all streams. */
  selectedIds: string[];
  onChange: (nextIds: string[]) => void;
}

const ACCENTS = [
  designTokens.semantic.primary,
  '#0d9488',
  '#7c3aed',
  '#c2410c',
  '#0369a1',
] as const;

function accentFor(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i += 1) {
    hash = (hash + label.charCodeAt(i) * (i + 1)) % ACCENTS.length;
  }
  return ACCENTS[hash] ?? ACCENTS[0];
}

function iconFor(label: string) {
  const lower = label.toLowerCase();
  if (lower.includes('mold')) return PrecisionManufacturingOutlinedIcon;
  if (lower.includes('cad')) return ArchitectureIcon;
  return HubOutlinedIcon;
}

export function ProjectStreamCards({
  options,
  selectedIds,
  onChange,
}: ProjectStreamCardsProps) {
  if (!options.length) return null;

  const allSelected = selectedIds.length === 0;
  const selectedSet = new Set(selectedIds);

  const selectAll = () => onChange([]);

  const toggleStream = (streamId: string) => {
    if (allSelected) {
      onChange([streamId]);
      return;
    }
    if (selectedSet.has(streamId)) {
      const next = selectedIds.filter((id) => id !== streamId);
      onChange(next.length === 0 || next.length === options.length ? [] : next);
      return;
    }
    const next = [...selectedIds, streamId];
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
        Streams
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: 'repeat(2, minmax(0, 1fr))',
            sm: 'repeat(3, minmax(0, 1fr))',
            md: `repeat(${Math.min(options.length + 1, 5)}, minmax(0, 1fr))`,
          },
          gap: 1,
        }}
      >
        <ButtonBase
          aria-pressed={allSelected}
          onClick={selectAll}
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 0.75,
            p: 1.25,
            borderRadius: `${designTokens.radius.md}px`,
            border: '1px solid',
            borderColor: allSelected ? designTokens.semantic.primary : 'divider',
            bgcolor: allSelected ? designTokens.semantic.primarySoft : designTokens.semantic.card,
            boxShadow: allSelected ? 'none' : designTokens.elevation.card,
            textAlign: 'left',
            transition: `border-color ${designTokens.motion.fast}, background-color ${designTokens.motion.fast}`,
          }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
            All streams
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {options.reduce((sum, option) => sum + option.activeCount, 0)} active
          </Typography>
        </ButtonBase>

        {options.map((option) => {
          const selected = !allSelected && selectedSet.has(option.id);
          const accent = accentFor(option.label);
          const Icon = iconFor(option.label);
          return (
            <ButtonBase
              key={option.id}
              aria-pressed={selected}
              onClick={() => toggleStream(option.id)}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                gap: 0.85,
                p: 1.25,
                borderRadius: `${designTokens.radius.md}px`,
                border: '1px solid',
                borderColor: selected ? accent : 'divider',
                bgcolor: selected ? `${accent}14` : designTokens.semantic.card,
                boxShadow: selected ? 'none' : designTokens.elevation.card,
                borderLeft: `3px solid ${accent}`,
                textAlign: 'left',
                transition: `border-color ${designTokens.motion.fast}, background-color ${designTokens.motion.fast}`,
                '&:hover': {
                  borderColor: accent,
                  bgcolor: selected ? `${accent}1f` : designTokens.semantic.neutralSoft,
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, width: '100%' }}>
                <Box
                  sx={{
                    width: 28,
                    height: 28,
                    borderRadius: `${designTokens.radius.sm}px`,
                    display: 'grid',
                    placeItems: 'center',
                    bgcolor: `${accent}18`,
                    color: accent,
                    flexShrink: 0,
                  }}
                >
                  <Icon sx={{ fontSize: 16 }} />
                </Box>
                <Typography
                  variant="subtitle2"
                  sx={{
                    fontWeight: 700,
                    lineHeight: 1.2,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {option.label}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 1.25 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: accent }}>
                  {option.activeCount} active
                </Typography>
                {option.pastCount > 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    {option.pastCount} past
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
