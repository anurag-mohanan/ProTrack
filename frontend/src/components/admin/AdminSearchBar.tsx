import { useMemo, useState } from 'react';
import {
  Autocomplete,
  Box,
  CircularProgress,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  customersApi,
  rolesApi,
  taskTypesApi,
  teamsApi,
  usersApi,
  nonProductiveCodesApi,
} from '../../api/resources';
import { fetchProjectTemplates } from '../../api/projectTemplates';

interface SearchOption {
  id: string;
  label: string;
  group: string;
  path: string;
}

interface AdminSearchBarProps {
  placeholder?: string;
}

export function AdminSearchBar({
  placeholder = 'Search users, customers, teams, templates…',
}: AdminSearchBarProps) {
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [open, setOpen] = useState(false);

  const searchQuery = useQuery({
    queryKey: ['admin-global-search'],
    queryFn: async () => {
      const [users, customers, teams, roles, taskTypes, npCodes, templates] =
        await Promise.all([
          usersApi.list(),
          customersApi.list(),
          teamsApi.list(),
          rolesApi.list(),
          taskTypesApi.list(),
          nonProductiveCodesApi.list(),
          fetchProjectTemplates(),
        ]);
      return { users, customers, teams, roles, taskTypes, npCodes, templates };
    },
    staleTime: 60_000,
    enabled: open,
  });

  const options = useMemo((): SearchOption[] => {
    if (!searchQuery.data) return [];
    const term = input.trim().toLowerCase();
    if (!term) return [];

    const matches: SearchOption[] = [];
    const push = (group: string, path: string, label: string, id: string) => {
      if (label.toLowerCase().includes(term)) {
        matches.push({ id: `${group}-${id}`, label, group, path });
      }
    };

    searchQuery.data.users.forEach((user) =>
      push('Users', '/admin/users', `${user.first_name} ${user.last_name}`, user.id),
    );
    searchQuery.data.customers.forEach((customer) =>
      push('Customers', '/admin/customers', customer.name, customer.id),
    );
    searchQuery.data.teams.forEach((team) =>
      push('Teams', '/admin/teams', team.name, team.id),
    );
    searchQuery.data.roles.forEach((role) =>
      push('Roles', '/admin/roles', role.name, role.id),
    );
    searchQuery.data.taskTypes.forEach((taskType) =>
      push('Task Types', '/admin/task-types', taskType.name, taskType.id),
    );
    searchQuery.data.npCodes.forEach((code) =>
      push('NP Codes', '/admin/non-productive-codes', code.code, code.id),
    );
    searchQuery.data.templates.forEach((template) =>
      push('Templates', '/admin/project-templates', template.name, template.id),
    );

    return matches.slice(0, 12);
  }, [input, searchQuery.data]);

  return (
    <Autocomplete
      freeSolo
      open={open}
      onOpen={() => setOpen(true)}
      onClose={() => setOpen(false)}
      options={options}
      groupBy={(option) => (typeof option === 'string' ? '' : option.group)}
      getOptionLabel={(option) => (typeof option === 'string' ? option : option.label)}
      inputValue={input}
      onInputChange={(_event, value) => setInput(value)}
      onChange={(_event, value) => {
        if (value && typeof value !== 'string') {
          navigate(value.path);
          setInput('');
        }
      }}
      loading={searchQuery.isLoading}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder={placeholder}
          size="small"
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps.input,
              startAdornment: (
                <>
                  <InputAdornment position="start">
                    {searchQuery.isFetching ? (
                      <CircularProgress size={16} />
                    ) : (
                      <SearchIcon fontSize="small" color="action" />
                    )}
                  </InputAdornment>
                  {params.slotProps.input.startAdornment}
                </>
              ),
            },
          }}
        />
      )}
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.id}>
          <Typography variant="body2">{option.label}</Typography>
        </Box>
      )}
      sx={{ width: '100%', maxWidth: 560 }}
    />
  );
}
