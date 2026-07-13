import {
  Alert,
  Box,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Grid,
  Typography,
} from '@mui/material';
import SecurityIcon from '@mui/icons-material/Security';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import {
  ALL_MODULES,
  ALL_SPECIAL_PERMISSIONS,
  MODULE_FINANCIAL_PLANNING,
  MODULE_HUMAN_RESOURCES,
  MODULE_LABELS,
  SPECIAL_PERMISSION_LABELS,
  type ModuleKey,
  type SpecialPermissionKey,
} from '../../config/accessControl';
import { FormSection } from '../ui/design-system';
import {
  defaultModulesForRole,
  defaultSpecialPermissionsForRole,
} from '../../utils/permissions';

interface UserAccessControlSectionProps {
  roleName: string;
  moduleAccess: ModuleKey[];
  specialPermissions: SpecialPermissionKey[];
  onModuleAccessChange: (modules: ModuleKey[]) => void;
  onSpecialPermissionsChange: (permissions: SpecialPermissionKey[]) => void;
}

export function UserAccessControlSection({
  roleName,
  moduleAccess,
  specialPermissions,
  onModuleAccessChange,
  onSpecialPermissionsChange,
}: UserAccessControlSectionProps) {
  const toggleModule = (module: ModuleKey, checked: boolean) => {
    const next = checked
      ? [...new Set([...moduleAccess, module])]
      : moduleAccess.filter((item) => item !== module);
    onModuleAccessChange(next);
  };

  const toggleSpecial = (permission: SpecialPermissionKey, checked: boolean) => {
    const next = checked
      ? [...new Set([...specialPermissions, permission])]
      : specialPermissions.filter((item) => item !== permission);
    onSpecialPermissionsChange(next);
  };

  const applyRoleDefaults = () => {
    onModuleAccessChange(defaultModulesForRole(roleName));
    onSpecialPermissionsChange(defaultSpecialPermissionsForRole(roleName));
  };

  return (
    <>
      <FormSection title="Module Access" icon={ViewModuleIcon}>
        <Grid size={{ xs: 12 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Only checked modules appear in the sidebar for this user. Grant{' '}
            <strong>Financial Planning</strong> to any user who should see commercial data
            (defaults on for Engineering Manager and Admin).
          </Typography>
          <Alert severity="info" sx={{ mb: 1.5 }}>
            Financial Planning and Human Resources are independent modules — tick them here when
            creating or editing users.
          </Alert>
          <FormGroup sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 0.5 }}>
            {ALL_MODULES.map((module) => (
              <FormControlLabel
                key={module}
                control={
                  <Checkbox
                    size="small"
                    checked={moduleAccess.includes(module)}
                    onChange={(event) => toggleModule(module, event.target.checked)}
                  />
                }
                label={
                  module === MODULE_FINANCIAL_PLANNING || module === MODULE_HUMAN_RESOURCES
                    ? `${MODULE_LABELS[module]} ★`
                    : MODULE_LABELS[module]
                }
              />
            ))}
          </FormGroup>
        </Grid>
      </FormSection>

      <FormSection title="Special Permissions" icon={SecurityIcon}>
        <Grid size={{ xs: 12 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Independent of role — grant explicit capabilities when needed.
          </Typography>
          <FormGroup sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 0.5 }}>
            {ALL_SPECIAL_PERMISSIONS.map((permission) => (
              <FormControlLabel
                key={permission}
                control={
                  <Checkbox
                    size="small"
                    checked={specialPermissions.includes(permission)}
                    onChange={(event) => toggleSpecial(permission, event.target.checked)}
                  />
                }
                label={SPECIAL_PERMISSION_LABELS[permission]}
              />
            ))}
          </FormGroup>
        </Grid>
      </FormSection>

      <Box sx={{ px: 1 }}>
        <Typography
          component="button"
          type="button"
          onClick={applyRoleDefaults}
          sx={{
            border: 0,
            background: 'none',
            color: 'primary.main',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 600,
            p: 0,
          }}
        >
          Reset to role defaults
        </Typography>
      </Box>
    </>
  );
}
