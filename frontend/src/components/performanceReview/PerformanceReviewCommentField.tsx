import type { ReactNode } from 'react';
import { Box, TextField, Typography } from '@mui/material';

type ReviewCommentFieldProps = {
  label: string;
  value: string;
  editable: boolean;
  viewOnly: boolean;
  minRows?: number;
  onChange: (value: string) => void;
};

export function ReviewCommentField({
  label,
  value,
  editable,
  viewOnly,
  minRows = 3,
  onChange,
}: ReviewCommentFieldProps) {
  if (!editable) {
    return (
      <Box
        sx={{
          flex: 1,
          minHeight: 108,
          boxSizing: 'border-box',
          p: 1.25,
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          bgcolor: viewOnly ? 'transparent' : 'action.hover',
        }}
      >
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
          {label}
        </Typography>
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
          {value.trim() ? value : '—'}
        </Typography>
      </Box>
    );
  }

  return (
    <TextField
      fullWidth
      size="small"
      multiline
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      minRows={minRows}
      sx={{
        flex: 1,
        '& .MuiInputBase-root': {
          alignItems: 'flex-start',
        },
        '& textarea': {
          resize: 'vertical',
        },
      }}
    />
  );
}
