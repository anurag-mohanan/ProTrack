import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import type { ModuleHome } from '../../navigation/moduleHomes';

interface ModuleHomeButtonProps {
  home: ModuleHome;
}

/** Minimal link back to the module homepage (layout-injected). */
export function ModuleHomeButton({ home }: ModuleHomeButtonProps) {
  return (
    <Button
      component={RouterLink}
      to={home.homePath}
      variant="text"
      size="small"
      startIcon={<ArrowBackRoundedIcon sx={{ fontSize: 18 }} />}
      sx={{
        alignSelf: 'flex-start',
        mb: 1,
        px: 0.75,
        minWidth: 0,
        fontWeight: 600,
        color: 'text.secondary',
        textTransform: 'none',
        '&:hover': { color: 'primary.main', bgcolor: 'action.hover' },
      }}
    >
      {home.homeLabel}
    </Button>
  );
}
