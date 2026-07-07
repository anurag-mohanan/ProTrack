import { Badge, Button } from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';

interface FilterButtonProps {
  activeCount?: number;
  onClick: () => void;
}

export function FilterButton({ activeCount = 0, onClick }: FilterButtonProps) {
  return (
    <Badge
      badgeContent={activeCount > 0 ? activeCount : undefined}
      color="primary"
      overlap="circular"
      sx={{ '& .MuiBadge-badge': { fontSize: '0.65rem', minWidth: 16, height: 16 } }}
    >
      <Button
        size="small"
        variant="outlined"
        startIcon={<FilterListIcon sx={{ fontSize: 18 }} />}
        onClick={onClick}
        sx={{
          minHeight: 32,
          px: 1.25,
          fontSize: '0.8125rem',
          fontWeight: 600,
          borderColor: 'divider',
          color: 'text.primary',
        }}
      >
        Filters
      </Button>
    </Badge>
  );
}
