import { Box, Typography } from '@mui/material';
import type { NonProductiveCode } from '../../types';
import { formatDisplayValue } from '../../utils/format';

interface TimesheetNpReferencePanelProps {
  codes: NonProductiveCode[];
}

export function TimesheetNpReferencePanel({ codes }: TimesheetNpReferencePanelProps) {
  const activeCodes = codes
    .filter((code) => code.is_active && !code.is_archived)
    .sort((left, right) => left.sort_order - right.sort_order || left.code.localeCompare(right.code));

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        maxHeight: { xs: 240, lg: 'none' },
        overflow: 'auto',
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
        Non Productive Codes
      </Typography>
      <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
        {activeCodes.map((code) => (
          <Box
            component="li"
            key={code.id}
            sx={{
              display: 'grid',
              gridTemplateColumns: '72px 1fr',
              gap: 1,
              py: 0.75,
              borderBottom: 1,
              borderColor: 'divider',
              '&:last-child': { borderBottom: 0 },
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              {formatDisplayValue(code.code)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatDisplayValue(code.description)}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
