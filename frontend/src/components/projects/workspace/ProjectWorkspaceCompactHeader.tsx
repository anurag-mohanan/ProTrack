import { Box, Typography } from '@mui/material';
import type { Project } from '../../../types';
import { PROJECT_STAGE_LABELS } from '../../../types/common';
import { designTokens } from '../../../theme/designTokens';
import { APP_TOP_BAR_OFFSET } from '../../ui/design-system/StickyRecordHeader';
import { formatDisplayValue, formatNumber } from '../../../utils/format';

interface ProjectWorkspaceCompactHeaderProps {
  project: Project;
}

export function ProjectWorkspaceCompactHeader({ project }: ProjectWorkspaceCompactHeaderProps) {
  const stageLabel = PROJECT_STAGE_LABELS[project.project_stage] ?? project.project_stage;

  return (
    <Box
      sx={{
        position: 'sticky',
        top: APP_TOP_BAR_OFFSET,
        zIndex: 3,
        mb: 1.5,
        px: 1.5,
        py: 1,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        boxShadow: (theme) => theme.palette.prosohm.shadowCard,
      }}
    >
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'auto 1fr auto' },
          gap: { xs: 1, md: 2 },
          alignItems: 'start',
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography
            sx={{
              fontSize: 22,
              fontWeight: 800,
              lineHeight: 1.1,
              color: designTokens.semantic.primary,
              letterSpacing: '-0.02em',
            }}
          >
            {formatDisplayValue(project.tool_number)}
          </Typography>
          <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', lineHeight: 1.25 }} noWrap>
            {formatDisplayValue(project.part_description)}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {formatDisplayValue(project.customer_name)}
          </Typography>
        </Box>

        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 2,
            alignItems: 'center',
            fontSize: '0.78rem',
          }}
        >
          <MetaItem label="Designer" value={formatDisplayValue(project.designer_name)} />
          <MetaItem label="Surfacer" value={formatDisplayValue(project.surfacer_name)} />
          <MetaItem label="Quoted" value={`${formatNumber(project.quoted_hours, 0)} hrs`} />
          <MetaItem label="Actual" value={`${formatNumber(project.actual_hours, 0)} hrs`} />
          <MetaItem label="Status" value={stageLabel} />
        </Box>
      </Box>
    </Box>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.1 }}>
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700, fontSize: '0.78rem', lineHeight: 1.2 }} noWrap>
        {value}
      </Typography>
    </Box>
  );
}
