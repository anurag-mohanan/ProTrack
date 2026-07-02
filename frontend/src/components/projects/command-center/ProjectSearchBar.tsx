import SearchIcon from '@mui/icons-material/Search';
import { InputAdornment, TextField } from '@mui/material';

interface ProjectSearchBarProps {
  value: string;
  onChange: (value: string) => void;
}

export function ProjectSearchBar({ value, onChange }: ProjectSearchBarProps) {
  return (
    <TextField
      fullWidth
      size="small"
      placeholder="Search by Tool Number, Part Description, Customer, Designer or Team..."
      value={value}
      onChange={(event) => onChange(event.target.value)}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
            </InputAdornment>
          ),
        },
      }}
      sx={{
        mb: 3,
        '& .MuiOutlinedInput-root': {
          borderRadius: 2.5,
          bgcolor: 'background.paper',
          transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
          '&:hover': {
            boxShadow: (theme) => theme.palette.prosohm.shadowCard,
          },
          '&.Mui-focused': {
            boxShadow: (theme) => theme.palette.prosohm.shadowCardHover,
          },
        },
      }}
    />
  );
}
