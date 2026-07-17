import {
  Box,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { designTokens } from '../../theme/designTokens';
import { chartTheme } from '../../theme/chartTheme';
import { financeMoney } from './FinanceCockpitPrimitives';

export type AwardedQuoteRow = {
  id: string;
  tool_number: string;
  external_quote_number?: string | null;
  currency_code: string;
  current_revision: string;
  team_name?: string | null;
  customer_name?: string | null;
  project_linked?: boolean;
  quoted_revenue?: number | string | null;
  base_quoted_revenue_inr?: number | string | null;
  quoted_date?: string | null;
  invoiced_date?: string | null;
  is_invoiced?: boolean;
};

function StatusPill({
  label,
  tone,
}: {
  label: string;
  tone: 'success' | 'warning' | 'neutral';
}) {
  const palette =
    tone === 'success'
      ? { bg: designTokens.semantic.successSoft, fg: designTokens.semantic.success }
      : tone === 'warning'
        ? { bg: designTokens.semantic.warningSoft, fg: designTokens.semantic.warning }
        : { bg: designTokens.semantic.neutralSoft, fg: designTokens.semantic.neutral };

  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        px: 1,
        py: 0.25,
        borderRadius: `${designTokens.radius.sm}px`,
        bgcolor: palette.bg,
        color: palette.fg,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.02em',
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </Box>
  );
}

export function FinanceQuotesTable<T extends AwardedQuoteRow>({
  rows,
  emptyMessage,
  onEdit,
  onDelete,
}: {
  rows: T[];
  emptyMessage: string;
  onEdit: (row: T) => void;
  onDelete: (row: T) => void;
}) {
  return (
    <TableContainer
      sx={{
        borderRadius: `${designTokens.radius.md}px`,
        border: `1px solid ${chartTheme.surface.hairline}`,
        bgcolor: designTokens.semantic.card,
        overflow: 'auto',
      }}
    >
      <Table size="small" stickyHeader sx={{ minWidth: 920 }}>
        <TableHead>
          <TableRow>
            <TableCell
              sx={{
                fontWeight: 700,
                bgcolor: designTokens.semantic.neutralSoft,
                color: chartTheme.ink.primary,
                borderBottom: `1px solid ${chartTheme.surface.hairline}`,
                minWidth: 200,
              }}
            >
              Quote
            </TableCell>
            <TableCell
              sx={{
                fontWeight: 700,
                bgcolor: designTokens.semantic.neutralSoft,
                color: chartTheme.ink.primary,
                borderBottom: `1px solid ${chartTheme.surface.hairline}`,
                minWidth: 180,
              }}
            >
              Customer
            </TableCell>
            <TableCell
              align="right"
              sx={{
                fontWeight: 700,
                bgcolor: designTokens.semantic.neutralSoft,
                color: chartTheme.ink.primary,
                borderBottom: `1px solid ${chartTheme.surface.hairline}`,
                minWidth: 140,
              }}
            >
              Amount
            </TableCell>
            <TableCell
              sx={{
                fontWeight: 700,
                bgcolor: designTokens.semantic.neutralSoft,
                color: chartTheme.ink.primary,
                borderBottom: `1px solid ${chartTheme.surface.hairline}`,
                minWidth: 130,
              }}
            >
              Dates
            </TableCell>
            <TableCell
              sx={{
                fontWeight: 700,
                bgcolor: designTokens.semantic.neutralSoft,
                color: chartTheme.ink.primary,
                borderBottom: `1px solid ${chartTheme.surface.hairline}`,
                minWidth: 160,
              }}
            >
              Status
            </TableCell>
            <TableCell
              align="right"
              sx={{
                fontWeight: 700,
                bgcolor: designTokens.semantic.neutralSoft,
                color: chartTheme.ink.primary,
                borderBottom: `1px solid ${chartTheme.surface.hairline}`,
                width: 96,
              }}
            >
              Actions
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} sx={{ py: 4 }}>
                <Typography variant="body2" color="text.secondary" align="center">
                  {emptyMessage}
                </Typography>
              </TableCell>
            </TableRow>
          ) : (
            rows.map((quote) => {
              const currency = (quote.currency_code || 'INR').toUpperCase();
              const quoteLabel = quote.external_quote_number?.trim() || quote.tool_number;
              const showFx =
                quote.base_quoted_revenue_inr != null && currency !== 'INR';

              return (
                <TableRow
                  key={quote.id}
                  hover
                  sx={{
                    '&:last-child td': { borderBottom: 0 },
                    '& td': { borderColor: chartTheme.surface.hairline, py: 1.35 },
                  }}
                >
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700, color: chartTheme.ink.primary, letterSpacing: '-0.01em' }}
                    >
                      {quoteLabel}
                    </Typography>
                    <Typography variant="caption" sx={{ color: chartTheme.ink.secondary, display: 'block' }}>
                      Project {quote.tool_number}
                      {quote.current_revision ? ` · Rev ${quote.current_revision}` : ''}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: chartTheme.ink.primary }}>
                      {quote.customer_name ?? 'Customer'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: chartTheme.ink.secondary, display: 'block' }}>
                      {quote.team_name ?? 'No team'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700, color: chartTheme.ink.primary, fontVariantNumeric: 'tabular-nums' }}
                    >
                      {financeMoney(quote.quoted_revenue, currency)}
                    </Typography>
                    {showFx ? (
                      <Typography
                        variant="caption"
                        sx={{ color: chartTheme.ink.secondary, display: 'block', fontVariantNumeric: 'tabular-nums' }}
                      >
                        ≈ {financeMoney(quote.base_quoted_revenue_inr, 'INR')}
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ color: chartTheme.ink.secondary, display: 'block' }}>
                      Quoted {quote.quoted_date ?? '—'}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        display: 'block',
                        fontWeight: quote.is_invoiced ? 600 : 500,
                        color: quote.is_invoiced
                          ? designTokens.semantic.success
                          : designTokens.semantic.warning,
                      }}
                    >
                      {quote.is_invoiced && quote.invoiced_date
                        ? `Invoiced ${quote.invoiced_date}`
                        : 'Not invoiced'}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap' }}>
                      <StatusPill
                        label={quote.project_linked ? 'Linked' : 'Unlinked'}
                        tone={quote.project_linked ? 'success' : 'neutral'}
                      />
                      <StatusPill
                        label={quote.is_invoiced ? 'Invoiced' : 'Pending'}
                        tone={quote.is_invoiced ? 'success' : 'warning'}
                      />
                      {!quote.quoted_date ? <StatusPill label="No date" tone="warning" /> : null}
                    </Stack>
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.25} sx={{ justifyContent: 'flex-end' }}>
                      <Tooltip title="Edit quote">
                        <IconButton
                          size="small"
                          aria-label="Edit quote"
                          onClick={() => onEdit(quote)}
                          sx={{
                            color: designTokens.semantic.primary,
                            bgcolor: designTokens.semantic.primarySoft,
                            borderRadius: `${designTokens.radius.sm}px`,
                            '&:hover': { bgcolor: designTokens.semantic.primarySoft },
                          }}
                        >
                          <EditOutlinedIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete quote">
                        <IconButton
                          size="small"
                          aria-label="Delete quote"
                          onClick={() => onDelete(quote)}
                          sx={{
                            color: designTokens.semantic.danger,
                            bgcolor: designTokens.semantic.dangerSoft,
                            borderRadius: `${designTokens.radius.sm}px`,
                            '&:hover': { bgcolor: designTokens.semantic.dangerSoft },
                          }}
                        >
                          <DeleteOutlinedIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
