import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
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
    <Accordion
      disableGutters
      elevation={0}
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: '8px !important',
        mb: 2,
        '&:before': { display: 'none' },
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 44 }}>
        <Typography variant="body2" sx={{ fontWeight: 700 }}>
          Non-Productive Codes
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        <Box component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
          {activeCodes.map((code) => (
            <Box
              component="li"
              key={code.id}
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '72px 1fr', sm: '80px 1fr' },
                gap: 1,
                py: 0.5,
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
      </AccordionDetails>
    </Accordion>
  );
}
