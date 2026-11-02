import { useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  Collapse,
  IconButton,
  Link,
  Paper,
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
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import ThumbUpAltOutlinedIcon from '@mui/icons-material/ThumbUpAltOutlined';
import ThumbUpAltRoundedIcon from '@mui/icons-material/ThumbUpAltRounded';
import ThumbDownAltOutlinedIcon from '@mui/icons-material/ThumbDownAltOutlined';
import ThumbDownAltRoundedIcon from '@mui/icons-material/ThumbDownAltRounded';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { Link as RouterLink } from 'react-router-dom';
import type { AssistantMessage, AssistantTable } from '../../api/assistant';
import { formatDateTime } from '../../utils/format';

const SOURCE_PREVIEW = 12;

function cellText(value: string | number | boolean | null): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return value;
}

function DataTable({ table }: { table: AssistantTable }) {
  return (
    <Box sx={{ mt: 1.5 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
        {table.title} · {table.rows.length} row{table.rows.length === 1 ? '' : 's'}
      </Typography>
      <TableContainer component={Paper} variant="outlined" sx={{ mt: 0.5, maxHeight: 320 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              {table.columns.map((column) => (
                <TableCell key={column} sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
                  {column}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {table.rows.map((row, index) => (
              <TableRow key={index}>
                {row.map((value, cell) => (
                  <TableCell key={cell} sx={{ whiteSpace: typeof value === 'number' ? 'nowrap' : undefined }}>
                    {cellText(value)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

interface AssistantMessageViewProps {
  message: AssistantMessage;
  onAsk: (text: string) => void;
  onCopy: (text: string) => void;
  onFeedback: (rating: 'up' | 'down' | null) => void;
  disabled?: boolean;
}

export function AssistantMessageView({ message, onAsk, onCopy, onFeedback, disabled }: AssistantMessageViewProps) {
  const [showAllSources, setShowAllSources] = useState(false);
  const [showLimitations, setShowLimitations] = useState(false);

  if (message.role === 'user') {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Paper
          elevation={0}
          sx={{ px: 2, py: 1.25, maxWidth: '80%', bgcolor: 'primary.main', color: 'primary.contrastText', borderRadius: 2 }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {message.content}
          </Typography>
        </Paper>
      </Box>
    );
  }

  const sources = showAllSources ? message.sources : message.sources.slice(0, SOURCE_PREVIEW);
  const severity = message.status === 'error' ? 'error' : message.status === 'offline' ? 'info' : null;

  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      {severity ? (
        <Alert severity={severity} sx={{ mb: message.tables.length ? 1 : 0 }}>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {message.content}
          </Typography>
        </Alert>
      ) : (
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {message.content}
        </Typography>
      )}

      {message.tables.map((table, index) => (
        <DataTable key={`${table.title}-${index}`} table={table} />
      ))}

      {message.recommendations.length ? (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
            Recommendations recorded for review (nothing has been changed)
          </Typography>
          <Stack sx={{ mt: 0.5, gap: 0.5 }}>
            {message.recommendations.map((rec) => (
              <Link key={rec.id} component={RouterLink} to="/assistant?tab=recommendations" variant="body2">
                {rec.title} · {rec.priority} priority · {rec.status}
              </Link>
            ))}
          </Stack>
        </Box>
      ) : null}

      {message.sources.length ? (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
            Sources ({message.sources.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
            {sources.map((source) =>
              source.route ? (
                <Chip
                  key={source.key}
                  size="small"
                  variant="outlined"
                  clickable
                  component={RouterLink}
                  to={source.route}
                  label={source.label}
                  title={source.detail ?? source.kind}
                />
              ) : (
                <Chip key={source.key} size="small" variant="outlined" label={source.label} title={source.detail ?? source.kind} />
              ),
            )}
            {message.sources.length > SOURCE_PREVIEW ? (
              <Chip
                size="small"
                label={showAllSources ? 'Show fewer' : `+${message.sources.length - SOURCE_PREVIEW} more`}
                onClick={() => setShowAllSources((v) => !v)}
              />
            ) : null}
          </Box>
        </Box>
      ) : null}

      {message.limitations.length ? (
        <Box sx={{ mt: 1.5 }}>
          <Link
            component="button"
            type="button"
            variant="caption"
            onClick={() => setShowLimitations((v) => !v)}
            sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
          >
            <InfoOutlinedIcon sx={{ fontSize: 14 }} />
            {showLimitations ? 'Hide' : 'Show'} data limitations ({message.limitations.length})
          </Link>
          <Collapse in={showLimitations}>
            <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
              {message.limitations.map((note) => (
                <Typography key={note} component="li" variant="caption" color="text.secondary" sx={{ display: 'list-item' }}>
                  {note}
                </Typography>
              ))}
            </Box>
          </Collapse>
        </Box>
      ) : null}

      {message.follow_ups.length ? (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1.5 }}>
          {message.follow_ups.map((text) => (
            <Chip key={text} size="small" color="primary" variant="outlined" label={text} onClick={() => onAsk(text)} disabled={disabled} />
          ))}
        </Box>
      ) : null}

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1 }}>
        <Typography variant="caption" color="text.disabled" sx={{ flex: 1 }}>
          {formatDateTime(message.created_at)}
          {message.model ? ` · ${message.model}` : message.status === 'data' ? ' · direct from ProTrack data' : ''}
        </Typography>
        <Tooltip title="Copy answer">
          <IconButton size="small" aria-label="Copy answer" onClick={() => onCopy(message.content)}>
            <ContentCopyRoundedIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Helpful">
          <IconButton
            size="small"
            aria-label="Mark helpful"
            onClick={() => onFeedback(message.feedback === 'up' ? null : 'up')}
          >
            {message.feedback === 'up' ? (
              <ThumbUpAltRoundedIcon sx={{ fontSize: 16 }} color="primary" />
            ) : (
              <ThumbUpAltOutlinedIcon sx={{ fontSize: 16 }} />
            )}
          </IconButton>
        </Tooltip>
        <Tooltip title="Not helpful or incorrect">
          <IconButton
            size="small"
            aria-label="Mark not helpful"
            onClick={() => onFeedback(message.feedback === 'down' ? null : 'down')}
          >
            {message.feedback === 'down' ? (
              <ThumbDownAltRoundedIcon sx={{ fontSize: 16 }} color="error" />
            ) : (
              <ThumbDownAltOutlinedIcon sx={{ fontSize: 16 }} />
            )}
          </IconButton>
        </Tooltip>
      </Box>
    </Paper>
  );
}
