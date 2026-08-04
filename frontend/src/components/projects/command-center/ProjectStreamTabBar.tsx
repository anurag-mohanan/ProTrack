import { Box, ButtonBase, Typography } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

export interface ProjectStreamTabOption {
  id: string;
  label: string;
  count: number;
}

interface ProjectStreamTabBarProps {
  options: ProjectStreamTabOption[];
  value: string;
  onChange: (next: string) => void;
}

export function ProjectStreamTabBar({ options, value, onChange }: ProjectStreamTabBarProps) {
  if (options.length <= 1) return null;

  return (
    <Box
      role="tablist"
      aria-label="Streams"
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 0.75,
        mb: 0.75,
        pb: 0.25,
      }}
    >
      {options.map((option) => {
        const selected = option.id === value;
        return (
          <ButtonBase
            key={option.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.id)}
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
                borderColor: selected ? designTokens.semantic.primary : 'text.disabled',
                bgcolor: selected ? designTokens.semantic.primarySoft : designTokens.semantic.neutralSoft,
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
              sx={{
                ml: 0.6,
                fontWeight: 700,
                opacity: 0.75,
                lineHeight: 1.2,
              }}
            >
              {option.count}
            </Typography>
          </ButtonBase>
        );
      })}
    </Box>
  );
}
