import {
  FormControlLabel,
  FormHelperText,
  Grid,
  Switch,
  Tooltip,
  Typography,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { FormSection, FormSelect } from '../ui/design-system';

export interface UserKpiFormState {
  operational_role_type_id: string;
  kpi_engineering_productivity: boolean;
  kpi_capacity_planning: boolean;
  kpi_utilization: boolean;
  kpi_workload_planning: boolean;
  kpi_dashboard_productivity: boolean;
  reset_kpi_defaults: boolean;
}

export interface OperationalRoleOption {
  id: string;
  name: string;
  code: string;
  dashboard_profile: string;
}

interface RoleSelectOption {
  value: string;
  label: string;
}

const KPI_FIELDS: Array<{
  key: keyof UserKpiFormState;
  label: string;
  tooltip: string;
}> = [
  {
    key: 'kpi_engineering_productivity',
    label: 'Engineering Productivity',
    tooltip: 'Include this user in designer/surfacer productivity, hours, and delivery KPIs.',
  },
  {
    key: 'kpi_capacity_planning',
    label: 'Capacity Planning',
    tooltip: 'Include in capacity planning grids and team capacity calculations.',
  },
  {
    key: 'kpi_utilization',
    label: 'Utilization',
    tooltip: 'Include in utilization percentages and engineering workload heatmaps.',
  },
  {
    key: 'kpi_workload_planning',
    label: 'Workload Planning',
    tooltip: 'Include in workload graphs and designer assignment workload views.',
  },
  {
    key: 'kpi_dashboard_productivity',
    label: 'Dashboard Metrics',
    tooltip: 'Include in engineering dashboard productivity widgets and team rankings.',
  },
];

interface UserKpiConfigurationProps {
  value: UserKpiFormState;
  operationalRoles: OperationalRoleOption[];
  onChange: (next: UserKpiFormState) => void;
}

function LabelWithTip({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {label}
      <Tooltip title={tooltip}>
        <InfoOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
      </Tooltip>
    </span>
  );
}

export function UserKpiConfiguration({
  value,
  operationalRoles,
  onChange,
}: UserKpiConfigurationProps) {
  const selectedRole = operationalRoles.find((role) => role.id === value.operational_role_type_id);
  const roleOptions: RoleSelectOption[] = [
    { value: '', label: 'Select operational role' },
    ...operationalRoles.map((role) => ({ value: role.id, label: role.name })),
  ];

  return (
    <FormSection title="KPI Configuration" subtitle="Operational role and participation in engineering metrics">
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <FormSelect
            label="Operational Role"
            options={roleOptions}
            value={value.operational_role_type_id}
            onChange={(event) =>
              onChange({
                ...value,
                operational_role_type_id: String(event.target.value),
                reset_kpi_defaults: true,
              })
            }
          />
          {selectedRole ? (
            <FormHelperText>
              Dashboard profile: {selectedRole.dashboard_profile.replace('_', ' ')}
            </FormHelperText>
          ) : null}
        </Grid>
        <Grid size={{ xs: 12 }}>
          <FormControlLabel
            control={
              <Switch
                checked={value.reset_kpi_defaults}
                onChange={(event) => onChange({ ...value, reset_kpi_defaults: event.target.checked })}
              />
            }
            label="Apply operational role defaults on save"
          />
        </Grid>
        {KPI_FIELDS.map((field) => (
          <Grid key={field.key} size={{ xs: 12, sm: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(value[field.key])}
                  onChange={(event) =>
                    onChange({ ...value, [field.key]: event.target.checked, reset_kpi_defaults: false })
                  }
                />
              }
              label={<LabelWithTip label={field.label} tooltip={field.tooltip} />}
            />
          </Grid>
        ))}
        <Grid size={{ xs: 12 }}>
          <Typography variant="caption" color="text.secondary">
            Management and administration users are excluded from engineering productivity by default. Flags remain editable for exceptions.
          </Typography>
        </Grid>
      </Grid>
    </FormSection>
  );
}
