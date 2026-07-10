import { Autocomplete, Box, Chip, TextField, Typography, createFilterOptions } from '@mui/material';
import type { TimesheetToolOption } from './timesheetToolOptions';

interface TimesheetToolNumberSelectProps {
  label?: string;
  value: TimesheetToolOption | null;
  options: TimesheetToolOption[];
  disabled?: boolean;
  onChange: (option: TimesheetToolOption | null) => void;
  onInputChange?: (value: string) => void;
  inputRef?: React.Ref<HTMLInputElement>;
  onKeyDown?: React.KeyboardEventHandler;
}

const filterToolOptions = createFilterOptions<TimesheetToolOption>({
  stringify: (option) => `${option.label} ${option.searchText}`,
  trim: true,
});

const GROUP_ORDER: Record<string, number> = {
  'MY ASSIGNED PROJECTS': 0,
  'RECENTLY USED': 1,
  'ALL ACTIVE PROJECTS': 2,
  'NON PRODUCTIVE': 3,
};

function ProjectOptionDetail({ option }: { option: TimesheetToolOption }) {
  if (option.kind !== 'project') {
    return <Typography variant="body2">{option.label}</Typography>;
  }
  return (
    <Box sx={{ py: 0.25, width: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.25 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {option.toolNumber}
        </Typography>
        {option.executionStatus ? (
          <Chip size="small" label={option.executionStatus} variant="outlined" sx={{ height: 20 }} />
        ) : null}
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {option.partDescription}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {[
          option.customerName ? `Customer: ${option.customerName}` : null,
          option.designerName ? `Designer: ${option.designerName}` : null,
          option.surfacerName ? `Surfacer: ${option.surfacerName}` : null,
          option.projectStage ? `Stage: ${option.projectStage}` : null,
          option.workingModelName ? `Model: ${option.workingModelName}` : null,
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
  onInputChange,
  inputRef,
  onKeyDown,
}: TimesheetToolNumberSelectProps) {
  const sortedOptions = [...options].sort(
    (left, right) => (GROUP_ORDER[left.group] ?? 9) - (GROUP_ORDER[right.group] ?? 9),
  );

  return (
    <Autocomplete
      size="small"
      fullWidth
      openOnFocus
      autoHighlight
      handleHomeEndKeys
      disabled={disabled}
      options={sortedOptions}
      value={value}
      groupBy={(option) => option.group}
      getOptionLabel={(option) => option.label}
      isOptionEqualToValue={(left, right) => left.value === right.value}
      filterOptions={filterToolOptions}
      onChange={(_, option) => onChange(option)}
      onInputChange={(_, inputValue, reason) => {
        if (reason === 'input') {
          onInputChange?.(inputValue);
        }
      }}
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
          placeholder="Search tool, customer, designer, surfacer…"
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
        />
      )}
    />
  );
}
