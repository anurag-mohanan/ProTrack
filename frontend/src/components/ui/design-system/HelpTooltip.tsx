import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { Box, IconButton, Tooltip } from '@mui/material';

interface HelpTooltipProps {
  title: string;
  size?: 'small' | 'medium';
}

export function HelpTooltip({ title, size = 'small' }: HelpTooltipProps) {
  return (
    <Tooltip title={title} arrow enterDelay={250}>
      <Box component="span" sx={{ display: 'inline-flex', verticalAlign: 'middle', ml: 0.5 }}>
        <IconButton
          size={size}
          tabIndex={0}
          aria-label={title}
          sx={{ p: 0.25, color: 'text.secondary' }}
        >
          <InfoOutlinedIcon fontSize="inherit" />
        </IconButton>
      </Box>
    </Tooltip>
  );
}
