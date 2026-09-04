import { useMemo } from 'react';
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
  SPECIAL_APPROVE_TIMESHEETS,
  SPECIAL_IMPORT_TIMESHEETS,
  SPECIAL_PERMISSION_LABELS,
  type ModuleKey,
  type SpecialPermissionKey,
} from '../../config/accessControl';
import { FormSection } from '../ui/design-system';
import {
  defaultModulesForRole,
  defaultSpecialPermissionsForRole,
  ROLES,
} from '../../utils/permissions';

/** Mirrors selectable SoD pairs on the Users form (backend has additional finance pairs). */
const SOD_CONFLICT_PAIRS: Array<{
  left: SpecialPermissionKey;
  right: SpecialPermissionKey;
  message: string;
}> = [
  {
    left: SPECIAL_IMPORT_TIMESHEETS,
    right: SPECIAL_APPROVE_TIMESHEETS,
    message: 'Cannot both import and approve timesheets (maker-checker).',
  },
];

export function getSpecialPermissionSodConflicts(
  specialPermissions: SpecialPermissionKey[],
  roleName: string,
): Array<{ left: SpecialPermissionKey; right: SpecialPermissionKey; message: string }> {
  if (roleName === ROLES.ADMIN) return [];
  const held = new Set(specialPermissions);
  return SOD_CONFLICT_PAIRS.filter(({ left, right }) => held.has(left) && held.has(right));
}
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
  const sodConflicts = useMemo(
    () => getSpecialPermissionSodConflicts(specialPermissions, roleName),
    [roleName, specialPermissions],
  );
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
            <strong>Finance</strong>, <strong>Human Resources</strong>, and{' '}
            <strong>Reports &amp; Analytics</strong> here — they are listed below the classic
            modules (look for ★).
          </Typography>
          <Alert severity="info" sx={{ mb: 1.5 }}>
            Scroll this list: you should see Finance ★, Human Resources ★, and Reports
            &amp; Analytics after System Administration. If you only see eight modules, hard-refresh
            the browser (Ctrl+Shift+R) — you are on a cached page.
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
            Independent of role. Create Projects and Edit Projects are separate — viewing the
            Projects module does not grant either. They still apply only inside the user's team /
            data scope. Delete Projects can be combined with Approve Projects (soft-delete is
            recoverable).
          </Typography>
          {sodConflicts.length ? (
            <Alert severity="error" sx={{ mb: 1.5 }}>
              Segregation of duties conflict — remove one of each conflicting pair before saving:{' '}
              {sodConflicts
                .map(
                  ({ left, right, message }) =>
                    `${SPECIAL_PERMISSION_LABELS[left]} + ${SPECIAL_PERMISSION_LABELS[right]} (${message})`,
                )
                .join(' · ')}
            </Alert>
          ) : null}
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
            textDecoration: 'underline',
            fontSize: '0.875rem',
            p: 0,
          }}
        >
          Reset to role defaults
        </Typography>
      </Box>
    </>
  );
}
