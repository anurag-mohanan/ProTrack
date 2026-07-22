import { useState } from 'react';
import { InputAdornment, TextField } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useNavigate } from 'react-router-dom';

interface AppGlobalSearchBarProps {
  placeholder?: string;
  onSubmitted?: () => void;
  autoFocus?: boolean;
}

export function AppGlobalSearchBar({
  placeholder = 'Search projects, customers, teams…',
  onSubmitted,
  autoFocus = false,
}: AppGlobalSearchBarProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const submit = () => {
    const term = query.trim();
    if (!term) return;
    navigate(`/projects?search=${encodeURIComponent(term)}`);
    setQuery('');
    onSubmitted?.();
  };

  return (
    <TextField
      size="small"
      fullWidth
      id="global-search-input"
      aria-label="Global search"
      placeholder={placeholder}
      value={query}
      autoFocus={autoFocus}
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
        maxWidth: { xs: '100%', md: 420 },
        width: '100%',
        '& .MuiOutlinedInput-root': {
          borderRadius: 2.5,
          bgcolor: 'background.paper',
        },
      }}
    />
  );
}
