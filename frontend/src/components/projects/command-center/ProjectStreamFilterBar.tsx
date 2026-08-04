import { Box, ButtonBase, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

export interface ProjectStreamFilterOption {
  id: string;
  label: string;
  count: number;
}

interface ProjectStreamFilterBarProps {
  options: ProjectStreamFilterOption[];
  /** Empty selection means all streams. */
  selectedIds: string[];
  onChange: (nextIds: string[]) => void;
}

export function ProjectStreamFilterBar({
  options,
  selectedIds,
  onChange,
}: ProjectStreamFilterBarProps) {
  if (options.length === 0) return null;

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
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 0.75,
        mb: 0.75,
        pb: 0.25,
      }}
    >
      <Typography
        variant="caption"
        sx={{ fontWeight: 700, color: 'text.secondary', mr: 0.25, letterSpacing: '0.02em' }}
      >
        Streams
      </Typography>
      <ButtonBase
        aria-pressed={allSelected}
        onClick={selectAll}
        sx={{
          px: 1.1,
          py: 0.55,
          borderRadius: `${designTokens.radius.sm}px`,
          border: '1px solid',
          borderColor: allSelected ? designTokens.semantic.primary : 'divider',
          bgcolor: allSelected ? designTokens.semantic.primarySoft : designTokens.semantic.card,
          color: allSelected ? designTokens.semantic.primary : 'text.secondary',
          transition: `background-color ${designTokens.motion.fast}, border-color ${designTokens.motion.fast}`,
        }}
      >
        <Typography component="span" variant="caption" sx={{ fontWeight: allSelected ? 700 : 600 }}>
          All
        </Typography>
      </ButtonBase>
      {options.map((option) => {
        const selected = !allSelected && selectedSet.has(option.id);
        return (
          <ButtonBase
            key={option.id}
            aria-pressed={selected}
            onClick={() => toggleStream(option.id)}
            sx={{
              px: 1.1,
              py: 0.55,
              borderRadius: `${designTokens.radius.sm}px`,
              border: '1px solid',
              borderColor: selected ? designTokens.semantic.primary : 'divider',
              bgcolor: selected ? designTokens.semantic.primarySoft : designTokens.semantic.card,
              color: selected ? designTokens.semantic.primary : 'text.secondary',
              transition: `background-color ${designTokens.motion.fast}, border-color ${designTokens.motion.fast}`,
              '&:hover': {
                borderColor: designTokens.semantic.primary,
                bgcolor: selected
                  ? designTokens.semantic.primarySoft
                  : designTokens.semantic.neutralSoft,
              },
            }}
          >
            <Typography
              component="span"
              variant="caption"
              sx={{ fontWeight: selected ? 700 : 600, lineHeight: 1.2 }}
            >
              {option.label}
            </Typography>
            <Typography
              component="span"
              variant="caption"
              sx={{ ml: 0.6, fontWeight: 700, opacity: 0.75, lineHeight: 1.2 }}
            >
              {option.count}
            </Typography>
          </ButtonBase>
        );
      })}
    </Box>
  );
}
