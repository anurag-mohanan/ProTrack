import { useState } from 'react';
import { InputAdornment, TextField } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useNavigate } from 'react-router-dom';

interface AppGlobalSearchBarProps {
  placeholder?: string;
}

export function AppGlobalSearchBar({
  placeholder = 'Search projects, customers, teams…',
}: AppGlobalSearchBarProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const submit = () => {
    const term = query.trim();
    if (!term) return;
    navigate(`/projects?search=${encodeURIComponent(term)}`);
    setQuery('');
  };

  return (
    <TextField
      size="small"
      fullWidth
      id="global-search-input"
      aria-label="Global search"
      placeholder={placeholder}
      value={query}
      onChange={(event) => setQuery(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          submit();
        }
      }}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
            </InputAdornment>
          ),
        },
      }}
      sx={{
        maxWidth: 420,
        '& .MuiOutlinedInput-root': {
          borderRadius: 2.5,
          bgcolor: 'background.paper',
        },
      }}
    />
  );
}
