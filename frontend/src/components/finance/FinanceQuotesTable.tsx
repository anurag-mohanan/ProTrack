import {
  Box,
  IconButton,
  Link,
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
import OpenInNewOutlinedIcon from '@mui/icons-material/OpenInNewOutlined';
import { Link as RouterLink } from 'react-router-dom';
import { designTokens } from '../../theme/designTokens';
import { chartTheme } from '../../theme/chartTheme';
import { financeMoney } from './FinanceCockpitPrimitives';
import { toFiniteNumber } from '../../utils/format';

export type AwardedQuoteRow = {
  id: string;
  tool_number: string;
  external_quote_number?: string | null;
  currency_code: string;
  current_revision: string;
  team_name?: string | null;
  customer_name?: string | null;
  project_id?: string | null;
  project_linked?: boolean;
  quoted_revenue?: number | string | null;
  base_quoted_revenue_inr?: number | string | null;
  quoted_date?: string | null;
  invoiced_date?: string | null;
  is_invoiced?: boolean;
  customer_po_number?: string | null;
  is_paid?: boolean;
  paid_date?: string | null;
  payment_follow_up_due?: boolean;
  payment_follow_up_on?: string | null;
  total_invoiced?: number | string | null;
  total_paid?: number | string | null;
  balance_due?: number | string | null;
  remaining_to_invoice?: number | string | null;
  invoice_status?: 'none' | 'partial' | 'full' | string | null;
  payment_status?: 'none' | 'partial' | 'full' | string | null;
  is_partially_invoiced?: boolean;
  is_partially_paid?: boolean;
  billing_ready?: boolean;
  billing_gaps?: string[];
};

function resolveInvoiceStatus(quote: AwardedQuoteRow): 'none' | 'partial' | 'full' {
  const quoted = toFiniteNumber(quote.quoted_revenue);
  const invoiced = toFiniteNumber(quote.total_invoiced);
  const remaining =
    quote.remaining_to_invoice != null
      ? toFiniteNumber(quote.remaining_to_invoice)
      : Math.max(0, quoted - invoiced);

  if (invoiced <= 0 && !(quote.is_invoiced && quoted > 0)) return 'none';
  if (invoiced <= 0) return 'none';

  // Amounts are source of truth — never show "Invoiced" when contract remains.
  if (quoted > 0 && remaining > 0.01) return 'partial';
  if (quoted > 0 && remaining <= 0.01) return 'full';

  if (quote.invoice_status === 'partial' || quote.is_partially_invoiced) return 'partial';
  if (quote.invoice_status === 'full') return 'full';
  // Quoted unknown: do not claim fully invoiced.
  return 'partial';
}

function resolvePaymentStatus(
  quote: AwardedQuoteRow,
  invoiceStatus: 'none' | 'partial' | 'full',
): 'none' | 'partial' | 'full' {
  const paid = toFiniteNumber(quote.total_paid);
  const due = toFiniteNumber(quote.balance_due);
  if (invoiceStatus === 'none' || paid <= 0) return 'none';
  if (invoiceStatus === 'partial') return 'partial';
  if (due > 0.01) return 'partial';
  return 'full';
}

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
              const invoiceStatus = resolveInvoiceStatus(quote);
              const paymentStatus = resolvePaymentStatus(quote, invoiceStatus);
              const remainingToInvoice =
                quote.remaining_to_invoice != null
                  ? toFiniteNumber(quote.remaining_to_invoice)
                  : Math.max(
                      0,
                      toFiniteNumber(quote.quoted_revenue) - toFiniteNumber(quote.total_invoiced),
                    );

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
                    {quote.project_id ? (
                      <Link
                        component={RouterLink}
                        to={`/projects/${quote.project_id}`}
                        variant="caption"
                        sx={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}
                      >
                        Open project <OpenInNewOutlinedIcon sx={{ fontSize: 12 }} />
                      </Link>
                    ) : null}
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
                        fontWeight: invoiceStatus !== 'none' ? 600 : 500,
                        color:
                          invoiceStatus !== 'none'
                            ? designTokens.semantic.success
                            : designTokens.semantic.warning,
                      }}
                    >
                      {invoiceStatus === 'partial' && quote.invoiced_date
                        ? `Partially invoiced ${quote.invoiced_date}`
                        : invoiceStatus === 'full' && quote.invoiced_date
                          ? `Invoiced ${quote.invoiced_date}`
                          : invoiceStatus === 'partial'
                            ? 'Partially invoiced'
                            : invoiceStatus === 'full'
                              ? 'Invoiced'
                              : 'Not invoiced'}
                    </Typography>
                    {quote.customer_po_number ? (
                      <Typography variant="caption" sx={{ color: chartTheme.ink.secondary, display: 'block' }}>
                        PO {quote.customer_po_number}
                      </Typography>
                    ) : null}
                    {invoiceStatus !== 'none' ? (
                      <Typography
                        variant="caption"
                        sx={{
                          display: 'block',
                          fontWeight: 600,
                          color:
                            toFiniteNumber(quote.balance_due) > 0 || invoiceStatus === 'partial'
                              ? designTokens.semantic.warning
                              : designTokens.semantic.success,
                        }}
                      >
                        Paid {financeMoney(quote.total_paid, currency)} / Invoiced{' '}
                        {financeMoney(quote.total_invoiced, currency)}
                        {toFiniteNumber(quote.balance_due) > 0
                          ? ` · Due ${financeMoney(quote.balance_due, currency)}`
                          : invoiceStatus === 'partial'
                            ? ` · Settled on invoices · Left ${financeMoney(remainingToInvoice, currency)}`
                            : ' · Settled'}
                      </Typography>
                    ) : null}
                    {toFiniteNumber(quote.balance_due) > 0 && quote.payment_follow_up_due ? (
                      <Typography variant="caption" sx={{ color: designTokens.semantic.warning, display: 'block' }}>
                        Follow up
                        {quote.payment_follow_up_on ? ` (${quote.payment_follow_up_on})` : ''}
                      </Typography>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap' }}>
                      <StatusPill
                        label={quote.project_linked ? 'Linked' : 'Unlinked'}
                        tone={quote.project_linked ? 'success' : 'neutral'}
                      />
                      <StatusPill
                        label={
                          invoiceStatus === 'partial'
                            ? 'Partially invoiced'
                            : invoiceStatus === 'full'
                              ? 'Invoiced'
                              : 'Pending'
                        }
                        tone={invoiceStatus === 'none' ? 'warning' : 'success'}
                      />
                      {invoiceStatus !== 'none' ? (
                        <StatusPill
                          label={
                            paymentStatus === 'partial'
                              ? toFiniteNumber(quote.balance_due) > 0
                                ? 'Partially paid'
                                : 'Paid on invoices'
                              : paymentStatus === 'full'
                                ? 'Paid'
                                : 'Unpaid'
                          }
                          tone={paymentStatus === 'full' ? 'success' : 'warning'}
                        />
                      ) : null}
                      {quote.payment_follow_up_due ? (
                        <StatusPill label="Follow up" tone="warning" />
                      ) : null}
                      {!quote.quoted_date ? <StatusPill label="No date" tone="warning" /> : null}
                      {quote.billing_ready === false ? (
                        <Tooltip
                          title={`Billing gaps: ${(quote.billing_gaps ?? []).join(', ') || 'incomplete'}`}
                        >
                          <Box component="span">
                            <StatusPill label="Needs billing setup" tone="warning" />
                          </Box>
                        </Tooltip>
                      ) : (
                        <StatusPill label="Billing ready" tone="success" />
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.25} sx={{ justifyContent: 'flex-end' }}>
                      {quote.project_id ? (
                        <Tooltip title="Open linked project">
                          <IconButton
                            size="small"
                            aria-label="Open linked project"
                            component={RouterLink}
                            to={`/projects/${quote.project_id}`}
                            sx={{
                              color: designTokens.semantic.primary,
                              bgcolor: designTokens.semantic.primarySoft,
                              borderRadius: `${designTokens.radius.sm}px`,
                            }}
                          >
                            <OpenInNewOutlinedIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      ) : null}
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
