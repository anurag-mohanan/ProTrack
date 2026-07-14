import { Box, Typography } from '@mui/material';
import type { NonProductiveCode } from '../../types';
import { designTokens } from '../../theme/designTokens';
import { formatDisplayValue } from '../../utils/format';

interface TimesheetNpReferencePanelProps {
  codes: NonProductiveCode[];
}

/**
 * Compact always-open NP code cheat-sheet for My Entries.
 * Intended as a narrow right rail — not a page-width accordion.
 */
export function TimesheetNpReferencePanel({ codes }: TimesheetNpReferencePanelProps) {
  const activeCodes = codes
    .filter((code) => code.is_active && !code.is_archived)
    .sort((left, right) => left.sort_order - right.sort_order || left.code.localeCompare(right.code));

  return (
    <Box
      component="aside"
      aria-label="Non-productive codes reference"
      sx={{
        width: '100%',
        maxWidth: { xs: '100%', md: 240 },
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        bgcolor: 'background.paper',
        boxShadow: designTokens.elevation.card,
        overflow: 'hidden',
        position: { md: 'sticky' },
        top: { md: 88 },
      }}
    >
      <Box
        sx={{
          px: 1.25,
          py: 1,
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: designTokens.semantic.neutralSoft,
        }}
      >
        <Typography
          sx={{
            fontWeight: 800,
            fontSize: '0.72rem',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'text.secondary',
          }}
        >
          NP Codes
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25, lineHeight: 1.3 }}>
          Use as Tool Number when logging non-productive time
        </Typography>
      </Box>

      <Box
        component="ul"
        sx={{
          m: 0,
          px: 1.25,
          py: 1,
          listStyle: 'none',
          maxHeight: { xs: 220, md: 'min(52vh, 420px)' },
          overflowY: 'auto',
        }}
      >
        {activeCodes.length === 0 ? (
          <Typography variant="caption" color="text.secondary">
            No active codes
          </Typography>
        ) : (
          activeCodes.map((code) => (
            <Box
              component="li"
              key={code.id}
              sx={{
                display: 'grid',
                gridTemplateColumns: '56px minmax(0, 1fr)',
                columnGap: 0.75,
                py: 0.55,
                borderBottom: '1px solid',
                borderColor: 'divider',
                '&:last-of-type': { borderBottom: 'none' },
              }}
            >
              <Typography
                variant="caption"
                sx={{ fontWeight: 800, fontVariantNumeric: 'tabular-nums', lineHeight: 1.35 }}
              >
                {formatDisplayValue(code.code)}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ lineHeight: 1.35 }}
                title={code.description ?? undefined}
              >
                {formatDisplayValue(code.description)}
              </Typography>
            </Box>
          ))
        )}
      </Box>
    </Box>
  );
}
