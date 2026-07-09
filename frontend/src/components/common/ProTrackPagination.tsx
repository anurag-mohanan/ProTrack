import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FirstPageIcon from '@mui/icons-material/FirstPage';
import LastPageIcon from '@mui/icons-material/LastPage';
import { PAGE_SIZE_OPTIONS } from '../../types/pagination';

export interface ProTrackPaginationProps {
  page: number;
  pageSize: number;
  total: number;
  pages: number;
  rangeStart: number;
  rangeEnd: number;
  loading?: boolean;
  pageSizeOptions?: readonly number[];
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  label?: string;
}

function buildPageNumbers(current: number, totalPages: number): number[] {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const start = Math.max(1, Math.min(current - 2, totalPages - 4));
  return Array.from({ length: 5 }, (_, index) => start + index);
}

export function ProTrackPagination({
  page,
  pageSize,
  total,
  pages,
  rangeStart,
  rangeEnd,
  loading = false,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  onPageChange,
  onPageSizeChange,
  label = 'records',
}: ProTrackPaginationProps) {
  const theme = useTheme();
  const compact = useMediaQuery(theme.breakpoints.down('md'));
  const [goToValue, setGoToValue] = useState(String(page));

  useEffect(() => {
    setGoToValue(String(page));
  }, [page]);

  const pageNumbers = useMemo(() => buildPageNumbers(page, pages), [page, pages]);

  if (total === 0) {
    return null;
  }

  const commitGoTo = () => {
    const parsed = Number(goToValue);
    if (!Number.isFinite(parsed)) return;
    onPageChange(Math.min(Math.max(1, parsed), pages));
  };

  return (
    <Box
      role="navigation"
      aria-label="Pagination"
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', lg: 'row' },
        alignItems: { xs: 'stretch', lg: 'center' },
        justifyContent: 'space-between',
        gap: 1.5,
        py: 1.5,
        px: { xs: 0.5, sm: 1 },
      }}
    >
      <Typography variant="body2" color="text.secondary">
        Showing {rangeStart}–{rangeEnd} of {total} {label}
      </Typography>

      <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center', justifyContent: 'center' }}>
        <IconButton
          size="small"
          aria-label="First page"
          disabled={loading || page <= 1}
          onClick={() => onPageChange(1)}
        >
          <FirstPageIcon fontSize="small" />
        </IconButton>
        <IconButton
          size="small"
          aria-label="Previous page"
          disabled={loading || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeftIcon fontSize="small" />
        </IconButton>

        {compact ? (
          <Typography variant="body2" sx={{ minWidth: 72, textAlign: 'center' }}>
            {page}/{pages}
          </Typography>
        ) : (
          pageNumbers.map((pageNumber) => (
            <IconButton
              key={pageNumber}
              size="small"
              aria-label={`Page ${pageNumber}`}
              aria-current={pageNumber === page ? 'page' : undefined}
              disabled={loading}
              onClick={() => onPageChange(pageNumber)}
              sx={{
                minWidth: 32,
                borderRadius: 1,
                fontWeight: pageNumber === page ? 700 : 500,
                bgcolor: pageNumber === page ? 'action.selected' : 'transparent',
              }}
            >
              {pageNumber}
            </IconButton>
          ))
        )}

        <IconButton
          size="small"
          aria-label="Next page"
          disabled={loading || page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRightIcon fontSize="small" />
        </IconButton>
        <IconButton
          size="small"
          aria-label="Last page"
          disabled={loading || page >= pages}
          onClick={() => onPageChange(pages)}
        >
          <LastPageIcon fontSize="small" />
        </IconButton>
      </Stack>

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1}
        sx={{ alignItems: 'center' }}
      >
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            Go to page:
          </Typography>
          <TextField
            size="small"
            value={goToValue}
            disabled={loading}
            onChange={(event) => setGoToValue(event.target.value)}
            onBlur={commitGoTo}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                commitGoTo();
              }
            }}
            slotProps={{
              htmlInput: {
                'aria-label': 'Go to page',
                inputMode: 'numeric',
                style: { width: 56, textAlign: 'center' },
              },
            }}
          />
        </Stack>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="pagination-page-size-label">Rows per page</InputLabel>
          <Select
            labelId="pagination-page-size-label"
            label="Rows per page"
            value={pageSize}
            disabled={loading}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            {pageSizeOptions.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>
    </Box>
  );
}
