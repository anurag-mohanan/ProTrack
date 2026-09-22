import { Box, Divider, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

export function ReviewSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
      <Typography variant="subtitle2" sx={{ mb: 1, letterSpacing: 0.4 }}>
        {title}
      </Typography>
      <Divider sx={{ mb: 1.25 }} />
      <Stack spacing={0.75}>{children}</Stack>
    </Box>
  );
}

export function ReviewRow({
  label,
  value,
  emphasize,
}: {
  label: string;
  value?: string | number | null;
  emphasize?: boolean;
}) {
  const display =
    value === null || value === undefined || String(value).trim() === ''
      ? '—'
      : String(value);
  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={0.5}
      sx={{ alignItems: { sm: 'baseline' } }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ minWidth: { sm: 180 }, flexShrink: 0 }}
      >
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: emphasize ? 700 : 500, wordBreak: 'break-word' }}
      >
        {display}
      </Typography>
    </Stack>
  );
}
