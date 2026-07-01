import { Box, Chip, Paper, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface AdminActionCardProps {
  title: string;
  description: string;
  icon: SvgIconComponent;
  path: string;
  comingSoon?: boolean;
}

export function AdminActionCard({
  title,
  description,
  icon: Icon,
  path,
  comingSoon = false,
}: AdminActionCardProps) {
  const navigate = useNavigate();

  return (
    <Paper
      elevation={0}
      onClick={() => {
        if (!comingSoon) navigate(path);
      }}
      sx={{
        p: 2.5,
        height: '100%',
        borderRadius: 3,
        border: '1px solid',
        borderColor: 'divider',
        cursor: comingSoon ? 'default' : 'pointer',
        opacity: comingSoon ? 0.72 : 1,
        transition: 'transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
        '&:hover': comingSoon
          ? undefined
          : {
              transform: 'translateY(-2px)',
              boxShadow: (theme) => theme.palette.prosohm.shadowCard,
              borderColor: 'primary.main',
            },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2,
            display: 'grid',
            placeItems: 'center',
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            flexShrink: 0,
          }}
        >
          <Icon />
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {title}
            </Typography>
            {comingSoon ? <Chip label="Soon" size="small" /> : null}
          </Box>
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
}
