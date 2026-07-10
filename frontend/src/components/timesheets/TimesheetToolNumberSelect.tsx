import { Autocomplete, Box, TextField, Typography, createFilterOptions } from '@mui/material';
import type { TimesheetToolOption } from './timesheetToolOptions';

interface TimesheetToolNumberSelectProps {
  label?: string;
  value: TimesheetToolOption | null;
  options: TimesheetToolOption[];
  disabled?: boolean;
  onChange: (option: TimesheetToolOption | null) => void;
  inputRef?: React.Ref<HTMLInputElement>;
  onKeyDown?: React.KeyboardEventHandler;
}

const filterToolOptions = createFilterOptions<TimesheetToolOption>({
  stringify: (option) => `${option.label} ${option.searchText}`,
  trim: true,
});

function ProjectOptionDetail({ option }: { option: TimesheetToolOption }) {
  if (option.kind !== 'project') {
    return <Typography variant="body2">{option.label}</Typography>;
  }
  return (
    <Box sx={{ py: 0.25 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {option.toolNumber}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {option.partDescription}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {[
          option.customerName ? `Customer: ${option.customerName}` : null,
          option.designerName ? `Designer: ${option.designerName}` : null,
          option.surfacerName ? `Surfacer: ${option.surfacerName}` : null,
          option.projectStage ? `Stage: ${option.projectStage}` : null,
        ]
          .filter(Boolean)
          .join(' · ')}
      </Typography>
    </Box>
  );
}

export function TimesheetToolNumberSelect({
  label = 'Tool Number',
  value,
  options,
  disabled,
  onChange,
  inputRef,
  onKeyDown,
}: TimesheetToolNumberSelectProps) {
  return (
    <Autocomplete
      size="small"
      fullWidth
      openOnFocus
      autoHighlight
      handleHomeEndKeys
      disabled={disabled}
      options={options}
      value={value}
      groupBy={(option) => option.group}
      getOptionLabel={(option) => option.label}
      isOptionEqualToValue={(left, right) => left.value === right.value}
      filterOptions={filterToolOptions}
      onChange={(_, option) => onChange(option)}
      noOptionsText="No matching tool numbers or NP codes"
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.value}>
          <ProjectOptionDetail option={option} />
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required
          size="small"
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          placeholder="Search tool number, customer, designer, surfacer…"
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />
      )}
    />
  );
}
