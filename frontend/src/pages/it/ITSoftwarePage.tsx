import { useMemo, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import AppsRoundedIcon from '@mui/icons-material/AppsRounded';
import type { GridColDef } from '@mui/x-data-grid';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSoftwareAssignment,
  createSoftwareCatalog,
  createSoftwareLicense,
  createSoftwareRequirement,
  deleteSoftwareRequirement,
  fetchSoftwareAssignments,
  fetchSoftwareCatalog,
  fetchSoftwareExpirySummary,
  fetchSoftwareInstallations,
  fetchSoftwareLicenses,
  fetchSoftwareRequirements,
  itOperationsKeys,
  renewSoftwareLicense,
  terminateSoftwareLicense,
  unassignSoftwareAssignment,
  uninstallSoftwareInstallation,
  updateSoftwareCatalog,
} from '../../api/itOperations';
import { fetchUsers } from '../../api/lookups';
import { getErrorMessage } from '../../api/client';
import { ClientPaginatedDataGrid } from '../../components/common/ClientPaginatedDataGrid';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { ITResourcePackagesPanel } from '../../components/it/ITResourcePackagesPanel';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import {
  FormDrawer,
  FormField,
  FormSection,
  FormSelect,
} from '../../components/ui/design-system';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type {
  EmployeeSoftwareRequirement,
  SoftwareAssignment,
  SoftwareCatalogItem,
  SoftwareInstallation,
  SoftwareLicensePool,
} from '../../types/itOperations';
import { formatCellValue, formatDate, userDisplayName } from '../../utils/format';
import { optionalString, validateRequiredFields } from '../../utils/formValues';
import { accessContextFromUser, canManageItAssets, canManageItSoftware } from '../../utils/permissions';

type TabKey =
  | 'catalog'
  | 'licenses'
  | 'assignments'
  | 'installations'
  | 'requirements'
  | 'packages'
  | 'expiry';

const TAB_TITLES: Record<TabKey, string> = {
  catalog: 'Software',
  licenses: 'Licenses',
  assignments: 'Assignments',
  installations: 'Installations',
  requirements: 'Requirements',
  packages: 'Packages',
  expiry: 'Renewals / Expiry',
};

const TAB_FROM_URL: Record<string, TabKey> = {
  '': 'catalog',
  software: 'catalog',
  catalog: 'catalog',
  licenses: 'licenses',
  assignments: 'assignments',
  installations: 'installations',
  expiry: 'expiry',
  requirements: 'requirements',
  packages: 'packages',
};

const ASSIGNMENT_MODEL_OPTIONS = [
  { value: 'named_user', label: 'Named user' },
  { value: 'floating', label: 'Floating' },
  { value: 'concurrent', label: 'Concurrent' },
  { value: 'device_bound', label: 'Device bound' },
  { value: 'network', label: 'Network' },
  { value: 'other', label: 'Other' },
];

const COMMERCIAL_MODEL_OPTIONS = [
  { value: 'subscription', label: 'Subscription' },
  { value: 'perpetual', label: 'Perpetual' },
];

const RENEWAL_FREQUENCY_OPTIONS = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'half_yearly', label: 'Half-yearly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'every_2_years', label: 'Every 2 years' },
  { value: 'custom', label: 'Custom' },
];

type CatalogForm = {
  name: string;
  vendor: string;
  version: string;
  edition: string;
  category: string;
  code: string;
  notes: string;
};

const emptyCatalog: CatalogForm = {
  name: '',
  vendor: '',
  version: '',
  edition: '',
  category: '',
  code: '',
  notes: '',
};

type LicenseForm = {
  software_id: string;
  seat_count: string;
  commercial_model: string;
  assignment_model: string;
  currency_code: string;
  cost: string;
  expiry_date: string;
  renewal_frequency: string;
  amc_required: string;
  amc_percent: string;
  notes: string;
};

const emptyLicense: LicenseForm = {
  software_id: '',
  seat_count: '1',
  commercial_model: 'subscription',
  assignment_model: 'named_user',
  currency_code: 'INR',
  cost: '',
  expiry_date: '',
  renewal_frequency: 'yearly',
  amc_required: 'no',
  amc_percent: '15',
  notes: '',
};

type AssignForm = {
  license_pool_id: string;
  user_id: string;
  notes: string;
};

const emptyAssign: AssignForm = {
  license_pool_id: '',
  user_id: '',
  notes: '',
};

type RequirementForm = {
  user_id: string;
  software_id: string;
  requirement_level: string;
  version: string;
  reason: string;
  notes: string;
};

const emptyRequirement: RequirementForm = {
  user_id: '',
  software_id: '',
  requirement_level: 'required',
  version: '',
  reason: '',
  notes: '',
};

export function ITSoftwarePage() {
  const { user } = useAuth();
  const access = accessContextFromUser(user);
  const canManage = canManageItSoftware(access);
  const canManagePackages = canManageItAssets(access);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  const [searchParams] = useSearchParams();
  const tab = TAB_FROM_URL[searchParams.get('tab') ?? ''] ?? 'catalog';
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [catalogForm, setCatalogForm] = useState<CatalogForm>(emptyCatalog);
  const [editingCatalog, setEditingCatalog] = useState<SoftwareCatalogItem | null>(null);
  const [licenseOpen, setLicenseOpen] = useState(false);
  const [licenseForm, setLicenseForm] = useState<LicenseForm>(emptyLicense);
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignForm, setAssignForm] = useState<AssignForm>(emptyAssign);
  const [requirementOpen, setRequirementOpen] = useState(false);
  const [requirementForm, setRequirementForm] = useState<RequirementForm>(emptyRequirement);
  const [terminateTarget, setTerminateTarget] = useState<SoftwareLicensePool | null>(null);
  const [terminateReason, setTerminateReason] = useState('');
  const [renewTarget, setRenewTarget] = useState<SoftwareLicensePool | null>(null);
  const [renewAmount, setRenewAmount] = useState('');
  const [renewPeriodEnd, setRenewPeriodEnd] = useState('');

  const catalogQuery = useQuery({
    queryKey: itOperationsKeys.software(),
    queryFn: () => fetchSoftwareCatalog(),
  });
  const licensesQuery = useQuery({
    queryKey: itOperationsKeys.softwareLicenses(),
    queryFn: () => fetchSoftwareLicenses(),
  });
  const assignmentsQuery = useQuery({
    queryKey: itOperationsKeys.softwareAssignments({ active_only: true }),
    queryFn: () => fetchSoftwareAssignments({ active_only: true }),
  });
  const installationsQuery = useQuery({
    queryKey: itOperationsKeys.softwareInstallations(),
    queryFn: () => fetchSoftwareInstallations(),
    enabled: tab === 'installations',
  });
  const requirementsQuery = useQuery({
    queryKey: itOperationsKeys.softwareRequirements(),
    queryFn: () => fetchSoftwareRequirements(),
  });
  const expiryQuery = useQuery({
    queryKey: itOperationsKeys.softwareExpiry(),
    queryFn: () => fetchSoftwareExpirySummary(30),
  });
  const usersQuery = useQuery({
    queryKey: ['lookups', 'users'],
    queryFn: () => fetchUsers(),
    enabled: canManage && (assignOpen || requirementOpen),
  });

  const softwareOptions = useMemo(
    () =>
      (catalogQuery.data ?? []).map((item) => ({
        value: item.id,
        label: item.vendor ? `${item.name} (${item.vendor})` : item.name,
      })),
    [catalogQuery.data],
  );

  const licenseOptions = useMemo(
    () =>
      (licensesQuery.data ?? [])
        .filter((pool) => {
          const status = (pool.status || 'active').toLowerCase();
          return status === 'active' || status === 'expiring_soon';
        })
        .filter((pool) => (pool.available_count ?? 0) > 0)
        .map((pool) => ({
          value: pool.id,
          label: `${pool.entitlement_code ? `${pool.entitlement_code} · ` : ''}${pool.software_name ?? 'Software'} — ${pool.available_count}/${pool.seat_count} available`,
        })),
    [licensesQuery.data],
  );

  const userOptions = useMemo(
    () =>
      (usersQuery.data ?? []).map((u) => ({
        value: u.id,
        label: userDisplayName(u) || u.email || u.id,
      })),
    [usersQuery.data],
  );

  const invalidateSoftware = () => {
    void queryClient.invalidateQueries({ queryKey: itOperationsKeys.all });
  };

  const catalogMutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: catalogForm.name.trim(),
        vendor: optionalString(catalogForm.vendor),
        version: optionalString(catalogForm.version),
        edition: optionalString(catalogForm.edition),
        category: optionalString(catalogForm.category),
        code: optionalString(catalogForm.code),
        notes: optionalString(catalogForm.notes),
      };
      if (editingCatalog) {
        return updateSoftwareCatalog(editingCatalog.id, payload);
      }
      return createSoftwareCatalog(payload);
    },
    onSuccess: () => {
      showSuccess(editingCatalog ? 'Software updated.' : 'Software added.');
      setCatalogOpen(false);
      setCatalogForm(emptyCatalog);
      setEditingCatalog(null);
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const licenseMutation = useMutation({
    mutationFn: () =>
      createSoftwareLicense({
        software_id: licenseForm.software_id,
        seat_count: Number(licenseForm.seat_count) || 1,
        commercial_model: optionalString(licenseForm.commercial_model) ?? undefined,
        assignment_model: optionalString(licenseForm.assignment_model) ?? undefined,
        license_type: optionalString(licenseForm.assignment_model) ?? undefined,
        currency_code: optionalString(licenseForm.currency_code),
        cost: licenseForm.cost ? Number(licenseForm.cost) : null,
        expiry_date: optionalString(licenseForm.expiry_date),
        renewal_frequency:
          licenseForm.commercial_model === 'subscription'
            ? optionalString(licenseForm.renewal_frequency)
            : null,
        amc_required:
          licenseForm.commercial_model === 'perpetual'
            ? licenseForm.amc_required === 'yes'
            : null,
        amc_percent:
          licenseForm.commercial_model === 'perpetual' && licenseForm.amc_required === 'yes'
            ? Number(licenseForm.amc_percent)
            : null,
        notes: optionalString(licenseForm.notes),
      }),
    onSuccess: () => {
      showSuccess('License pool created.');
      setLicenseOpen(false);
      setLicenseForm(emptyLicense);
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const terminateMutation = useMutation({
    mutationFn: () =>
      terminateSoftwareLicense(terminateTarget!.id, {
        termination_date: new Date().toISOString().slice(0, 10),
        reason: optionalString(terminateReason) || 'Terminated from IT Software',
      }),
    onSuccess: () => {
      showSuccess('License terminated.');
      setTerminateTarget(null);
      setTerminateReason('');
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const renewMutation = useMutation({
    mutationFn: () =>
      renewSoftwareLicense(renewTarget!.id, {
        amount: renewAmount ? Number(renewAmount) : null,
        period_end: optionalString(renewPeriodEnd),
      }),
    onSuccess: () => {
      showSuccess('Subscription renewed.');
      setRenewTarget(null);
      setRenewAmount('');
      setRenewPeriodEnd('');
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const assignMutation = useMutation({
    mutationFn: () =>
      createSoftwareAssignment({
        license_pool_id: assignForm.license_pool_id,
        user_id: optionalString(assignForm.user_id),
        notes: optionalString(assignForm.notes),
      }),
    onSuccess: () => {
      showSuccess('License assigned.');
      setAssignOpen(false);
      setAssignForm(emptyAssign);
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const unassignMutation = useMutation({
    mutationFn: (id: string) => unassignSoftwareAssignment(id),
    onSuccess: () => {
      showSuccess('License released.');
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const uninstallMutation = useMutation({
    mutationFn: (id: string) => uninstallSoftwareInstallation(id),
    onSuccess: () => {
      showSuccess('Installation marked uninstalled. License assignment is unchanged.');
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const requirementMutation = useMutation({
    mutationFn: () =>
      createSoftwareRequirement({
        user_id: requirementForm.user_id,
        software_id: requirementForm.software_id,
        requirement_level: requirementForm.requirement_level,
        version: optionalString(requirementForm.version),
        reason: optionalString(requirementForm.reason),
        notes: optionalString(requirementForm.notes),
      }),
    onSuccess: () => {
      showSuccess('Requirement saved.');
      setRequirementOpen(false);
      setRequirementForm(emptyRequirement);
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const deleteRequirementMutation = useMutation({
    mutationFn: (id: string) => deleteSoftwareRequirement(id),
    onSuccess: () => {
      showSuccess('Requirement removed.');
      invalidateSoftware();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const catalogColumns = useMemo<GridColDef<SoftwareCatalogItem>[]>(
    () => [
      { field: 'name', headerName: 'Name', flex: 1.2, minWidth: 160 },
      {
        field: 'vendor',
        headerName: 'Vendor',
        flex: 0.8,
        minWidth: 120,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'version',
        headerName: 'Version',
        width: 100,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'category',
        headerName: 'Category',
        width: 120,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'is_active',
        headerName: 'Active',
        width: 100,
        renderCell: (params) => (
          <Chip
            size="small"
            label={params.value ? 'Active' : 'Inactive'}
            color={params.value ? 'success' : 'default'}
          />
        ),
      },
      {
        field: 'actions',
        headerName: '',
        width: 100,
        sortable: false,
        renderCell: (params) =>
          canManage ? (
            <ProsohmButton
              size="small"
              buttonVariant="secondary"
              onClick={() => {
                setEditingCatalog(params.row);
                setCatalogForm({
                  name: params.row.name,
                  vendor: params.row.vendor ?? '',
                  version: params.row.version ?? '',
                  edition: params.row.edition ?? '',
                  category: params.row.category ?? '',
                  code: params.row.code ?? '',
                  notes: params.row.notes ?? '',
                });
                setCatalogOpen(true);
              }}
            >
              Edit
            </ProsohmButton>
          ) : null,
      },
    ],
    [canManage],
  );

  const licenseColumns = useMemo<GridColDef<SoftwareLicensePool>[]>(
    () => [
      {
        field: 'entitlement_code',
        headerName: 'License',
        width: 130,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'software_name',
        headerName: 'Software',
        flex: 1.1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'commercial_model',
        headerName: 'Commercial',
        width: 120,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        renderCell: (params) => {
          const status = String(params.row.status ?? 'active');
          const color =
            status === 'terminated' || status === 'expired' || status === 'cancelled'
              ? 'error'
              : status === 'expiring_soon'
                ? 'warning'
                : 'success';
          return <Chip size="small" color={color} variant="outlined" label={status} />;
        },
      },
      { field: 'seat_count', headerName: 'Total', width: 80 },
      { field: 'assigned_count', headerName: 'Assigned', width: 90 },
      { field: 'available_count', headerName: 'Available', width: 90 },
      {
        field: 'expiry_date',
        headerName: 'Renewal / Expiry',
        width: 130,
        valueFormatter: (value) => formatDate(value as string | null) || '—',
      },
      {
        field: 'amc_amount',
        headerName: 'AMC',
        width: 100,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'expense_id',
        headerName: 'Finance',
        width: 100,
        valueFormatter: (value) => (value ? 'Linked' : '—'),
      },
      {
        field: 'actions',
        headerName: '',
        width: 200,
        sortable: false,
        renderCell: (params) => {
          if (!canManage) return null;
          const status = (params.row.status || 'active').toLowerCase();
          const active = status === 'active' || status === 'expiring_soon';
          return (
            <Stack direction="row" spacing={0.5}>
              {active && params.row.commercial_model === 'subscription' ? (
                <ProsohmButton
                  size="small"
                  buttonVariant="secondary"
                  onClick={() => {
                    setRenewTarget(params.row);
                    setRenewAmount(
                      params.row.renewal_amount != null
                        ? String(params.row.renewal_amount)
                        : params.row.cost != null
                          ? String(params.row.cost)
                          : '',
                    );
                    setRenewPeriodEnd('');
                  }}
                >
                  Renew
                </ProsohmButton>
              ) : null}
              {active ? (
                <ProsohmButton
                  size="small"
                  buttonVariant="secondary"
                  onClick={() => {
                    setTerminateTarget(params.row);
                    setTerminateReason('');
                  }}
                >
                  Terminate
                </ProsohmButton>
              ) : null}
            </Stack>
          );
        },
      },
    ],
    [canManage],
  );

  const assignmentColumns = useMemo<GridColDef<SoftwareAssignment>[]>(
    () => [
      {
        field: 'software_name',
        headerName: 'Software',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'user_name',
        headerName: 'User',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'computer_name',
        headerName: 'Computer',
        width: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'assigned_date',
        headerName: 'Assigned',
        width: 120,
        valueFormatter: (value) => formatDate(value as string | null) || '—',
      },
      {
        field: 'actions',
        headerName: '',
        width: 120,
        sortable: false,
        renderCell: (params) =>
          canManage && params.row.is_active ? (
            <ProsohmButton
              size="small"
              buttonVariant="secondary"
              onClick={() => unassignMutation.mutate(params.row.id)}
            >
              Release
            </ProsohmButton>
          ) : null,
      },
    ],
    [canManage, unassignMutation],
  );

  const requirementColumns = useMemo<GridColDef<EmployeeSoftwareRequirement>[]>(
    () => [
      {
        field: 'user_name',
        headerName: 'Employee',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'software_name',
        headerName: 'Software',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      { field: 'requirement_level', headerName: 'Level', width: 110 },
      {
        field: 'version',
        headerName: 'Version',
        width: 100,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'reason',
        headerName: 'Reason',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'actions',
        headerName: '',
        width: 110,
        sortable: false,
        renderCell: (params) =>
          canManage ? (
            <ProsohmButton
              size="small"
              buttonVariant="secondary"
              onClick={() => deleteRequirementMutation.mutate(params.row.id)}
            >
              Remove
            </ProsohmButton>
          ) : null,
      },
    ],
    [canManage, deleteRequirementMutation],
  );

  const installationColumns = useMemo<GridColDef<SoftwareInstallation>[]>(
    () => [
      {
        field: 'software_name',
        headerName: 'Software',
        flex: 1.1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'computer_name',
        headerName: 'Computer',
        flex: 1,
        minWidth: 140,
        valueFormatter: (value) => formatCellValue(value),
      },
      {
        field: 'installed_date',
        headerName: 'Installed',
        width: 120,
        valueFormatter: (value) => formatDate(value as string | null) || '—',
      },
      {
        field: 'uninstalled_date',
        headerName: 'Uninstalled',
        width: 120,
        valueFormatter: (value) => formatDate(value as string | null) || '—',
      },
      {
        field: 'is_active',
        headerName: 'Status',
        width: 110,
        renderCell: (params) => (
          <Chip
            size="small"
            label={params.value ? 'Installed' : 'Removed'}
            color={params.value ? 'success' : 'default'}
          />
        ),
      },
      {
        field: 'actions',
        headerName: '',
        width: 120,
        sortable: false,
        renderCell: (params) =>
          canManage && params.row.is_active ? (
            <ProsohmButton
              size="small"
              buttonVariant="secondary"
              onClick={() => uninstallMutation.mutate(params.row.id)}
            >
              Uninstall
            </ProsohmButton>
          ) : null,
      },
    ],
    [canManage, uninstallMutation],
  );

  const handleCatalogSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    const error = validateRequiredFields(catalogForm, [{ key: 'name', label: 'Name' }]);
    if (error) {
      showError(error);
      return;
    }
    catalogMutation.mutate();
  };

  const handleLicenseSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    const error = validateRequiredFields(licenseForm, [
      { key: 'software_id', label: 'Software' },
    ]);
    if (error) {
      showError(error);
      return;
    }
    licenseMutation.mutate();
  };

  const handleAssignSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    const error = validateRequiredFields(assignForm, [
      { key: 'license_pool_id', label: 'License pool' },
      { key: 'user_id', label: 'User' },
    ]);
    if (error) {
      showError(error);
      return;
    }
    assignMutation.mutate();
  };

  const handleRequirementSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    const error = validateRequiredFields(requirementForm, [
      { key: 'user_id', label: 'Employee' },
      { key: 'software_id', label: 'Software' },
    ]);
    if (error) {
      showError(error);
      return;
    }
    requirementMutation.mutate();
  };

  if (catalogQuery.isLoading) {
    return <LoadingState message="Loading software & licenses…" />;
  }

  if (catalogQuery.isError) {
    return (
      <ErrorState
        error={catalogQuery.error}
        title="Unable to load software catalog"
        onRetry={() => void catalogQuery.refetch()}
      />
    );
  }

  const expiry = expiryQuery.data;

  return (
    <PageContainer>
      <PageHeader
        title={`Software & Licenses — ${TAB_TITLES[tab]}`}
        subtitle="Catalog, seat pools, assignments, employee requirements, packages, and expiry alerts."
        action={
          canManage ? (
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {tab === 'catalog' && (
                <ProsohmButton
                  startIcon={<AddIcon />}
                  onClick={() => {
                    setEditingCatalog(null);
                    setCatalogForm(emptyCatalog);
                    setCatalogOpen(true);
                  }}
                >
                  Add software
                </ProsohmButton>
              )}
              {tab === 'licenses' && (
                <ProsohmButton
                  startIcon={<AddIcon />}
                  onClick={() => {
                    setLicenseForm(emptyLicense);
                    setLicenseOpen(true);
                  }}
                >
                  Add license pool
                </ProsohmButton>
              )}
              {tab === 'assignments' && (
                <ProsohmButton
                  startIcon={<AddIcon />}
                  onClick={() => {
                    setAssignForm(emptyAssign);
                    setAssignOpen(true);
                  }}
                >
                  Assign license
                </ProsohmButton>
              )}
              {tab === 'requirements' && (
                <ProsohmButton
                  startIcon={<AddIcon />}
                  onClick={() => {
                    setRequirementForm(emptyRequirement);
                    setRequirementOpen(true);
                  }}
                >
                  Add requirement
                </ProsohmButton>
              )}
            </Stack>
          ) : undefined
        }
      />

      {tab === 'catalog' && (
        <ContentCard>
          {(catalogQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="No software yet"
              description="Add catalog entries that license pools and requirements will reference."
              icon={<AppsRoundedIcon />}
            />
          ) : (
            <ClientPaginatedDataGrid rows={catalogQuery.data ?? []} columns={catalogColumns} />
          )}
        </ContentCard>
      )}

      {tab === 'licenses' && (
        <ContentCard>
          {licensesQuery.isLoading ? (
            <LoadingState message="Loading licenses…" />
          ) : (licensesQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="No license pools"
              description="Create seat pools against catalog software to track capacity and expiry."
            />
          ) : (
            <ClientPaginatedDataGrid rows={licensesQuery.data ?? []} columns={licenseColumns} />
          )}
        </ContentCard>
      )}

      {tab === 'assignments' && (
        <ContentCard>
          {assignmentsQuery.isLoading ? (
            <LoadingState message="Loading assignments…" />
          ) : (assignmentsQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="No active assignments"
              description="Assign seats from a license pool to employees (and optionally computers)."
            />
          ) : (
            <ClientPaginatedDataGrid
              rows={assignmentsQuery.data ?? []}
              columns={assignmentColumns}
            />
          )}
        </ContentCard>
      )}

      {tab === 'installations' && (
        <ContentCard>
          {installationsQuery.isLoading ? (
            <LoadingState message="Loading installations…" />
          ) : (installationsQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="No installations recorded"
              description="Installations are created when a license is assigned to a computer. Uninstall does not release the license."
            />
          ) : (
            <ClientPaginatedDataGrid
              rows={installationsQuery.data ?? []}
              columns={installationColumns}
            />
          )}
        </ContentCard>
      )}

      {tab === 'requirements' && (
        <ContentCard>
          {requirementsQuery.isLoading ? (
            <LoadingState message="Loading requirements…" />
          ) : (requirementsQuery.data ?? []).length === 0 ? (
            <EmptyState
              title="No employee requirements"
              description="Record which software each employee must or may have for compliance checks."
            />
          ) : (
            <ClientPaginatedDataGrid
              rows={requirementsQuery.data ?? []}
              columns={requirementColumns}
            />
          )}
        </ContentCard>
      )}

      {tab === 'packages' && <ITResourcePackagesPanel canManage={canManagePackages} />}

      {tab === 'expiry' && (
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <Chip label={`Active pools: ${expiry?.active_count ?? 0}`} color="success" />
            <Chip
              label={`Expiring in 30 days: ${expiry?.expiring_30_count ?? 0}`}
              color="warning"
            />
            <Chip label={`Expired: ${expiry?.expired_count ?? 0}`} color="error" />
          </Stack>
          <ContentCard title="Expiring within 30 days">
            {(expiry?.expiring_30 ?? []).length === 0 ? (
              <Typography color="text.secondary">
                No licenses expiring in the next 30 days.
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Software</TableCell>
                    <TableCell>Seats</TableCell>
                    <TableCell>Available</TableCell>
                    <TableCell>Expiry</TableCell>
                    <TableCell>Type</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(expiry?.expiring_30 ?? []).map((row) => (
                    <TableRow key={String(row.id)}>
                      <TableCell>{String(row.software_name ?? '—')}</TableCell>
                      <TableCell>{String(row.seat_count ?? '—')}</TableCell>
                      <TableCell>{String(row.available_count ?? '—')}</TableCell>
                      <TableCell>
                        {formatDate(row.expiry_date as string | null) || '—'}
                      </TableCell>
                      <TableCell>{String(row.license_type ?? '—')}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ContentCard>
          <ContentCard title="Expired">
            {(expiry?.expired ?? []).length === 0 ? (
              <Typography color="text.secondary">No expired license pools.</Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Software</TableCell>
                    <TableCell>Seats</TableCell>
                    <TableCell>Expiry</TableCell>
                    <TableCell>Renewal</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(expiry?.expired ?? []).map((row) => (
                    <TableRow key={String(row.id)}>
                      <TableCell>{String(row.software_name ?? '—')}</TableCell>
                      <TableCell>{String(row.seat_count ?? '—')}</TableCell>
                      <TableCell>
                        {formatDate(row.expiry_date as string | null) || '—'}
                      </TableCell>
                      <TableCell>{String(row.renewal_mode ?? '—')}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </ContentCard>
        </Stack>
      )}

      <FormDrawer
        open={catalogOpen}
        onClose={() => setCatalogOpen(false)}
        title={editingCatalog ? 'Edit software' : 'Add software'}
        formId="it-software-catalog-form"
        submitLabel={editingCatalog ? 'Save' : 'Create'}
        loading={catalogMutation.isPending}
        icon={AppsRoundedIcon}
      >
        <Box
          component="form"
          id="it-software-catalog-form"
          onSubmit={handleCatalogSubmit}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Catalog">
            <FormField
              label="Name"
              required
              value={catalogForm.name}
              onChange={(e) => setCatalogForm((f) => ({ ...f, name: e.target.value }))}
            />
            <FormField
              label="Vendor"
              value={catalogForm.vendor}
              onChange={(e) => setCatalogForm((f) => ({ ...f, vendor: e.target.value }))}
            />
            <FormField
              label="Version"
              value={catalogForm.version}
              onChange={(e) => setCatalogForm((f) => ({ ...f, version: e.target.value }))}
            />
            <FormField
              label="Edition"
              value={catalogForm.edition}
              onChange={(e) => setCatalogForm((f) => ({ ...f, edition: e.target.value }))}
            />
            <FormField
              label="Category"
              value={catalogForm.category}
              onChange={(e) => setCatalogForm((f) => ({ ...f, category: e.target.value }))}
            />
            <FormField
              label="Code"
              value={catalogForm.code}
              onChange={(e) => setCatalogForm((f) => ({ ...f, code: e.target.value }))}
            />
            <FormField
              label="Notes"
              multiline
              minRows={2}
              value={catalogForm.notes}
              onChange={(e) => setCatalogForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <FormDrawer
        open={licenseOpen}
        onClose={() => setLicenseOpen(false)}
        title="Add license pool"
        formId="it-software-license-form"
        submitLabel="Create"
        loading={licenseMutation.isPending}
      >
        <Box
          component="form"
          id="it-software-license-form"
          onSubmit={handleLicenseSubmit}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="License">
            <FormSelect
              label="Software"
              required
              value={licenseForm.software_id}
              onChange={(e) =>
                setLicenseForm((f) => ({ ...f, software_id: String(e.target.value) }))
              }
              options={softwareOptions}
            />
            <FormField
              label="Seat count"
              type="number"
              value={licenseForm.seat_count}
              onChange={(e) => setLicenseForm((f) => ({ ...f, seat_count: e.target.value }))}
            />
            <FormSelect
              label="Commercial model"
              value={licenseForm.commercial_model}
              onChange={(e) =>
                setLicenseForm((f) => ({ ...f, commercial_model: String(e.target.value) }))
              }
              options={COMMERCIAL_MODEL_OPTIONS}
            />
            <FormSelect
              label="Assignment model"
              value={licenseForm.assignment_model}
              onChange={(e) =>
                setLicenseForm((f) => ({ ...f, assignment_model: String(e.target.value) }))
              }
              options={ASSIGNMENT_MODEL_OPTIONS}
            />
            <FormField
              label="Currency"
              value={licenseForm.currency_code}
              onChange={(e) => setLicenseForm((f) => ({ ...f, currency_code: e.target.value }))}
            />
            <FormField
              label="Cost"
              type="number"
              value={licenseForm.cost}
              onChange={(e) => setLicenseForm((f) => ({ ...f, cost: e.target.value }))}
            />
            {licenseForm.commercial_model === 'subscription' ? (
              <>
                <FormSelect
                  label="Renewal frequency"
                  value={licenseForm.renewal_frequency}
                  onChange={(e) =>
                    setLicenseForm((f) => ({
                      ...f,
                      renewal_frequency: String(e.target.value),
                    }))
                  }
                  options={RENEWAL_FREQUENCY_OPTIONS}
                />
                <FormField
                  label="Next renewal / expiry"
                  type="date"
                  value={licenseForm.expiry_date}
                  onChange={(e) =>
                    setLicenseForm((f) => ({ ...f, expiry_date: e.target.value }))
                  }
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </>
            ) : (
              <>
                <FormSelect
                  label="AMC required"
                  value={licenseForm.amc_required}
                  onChange={(e) =>
                    setLicenseForm((f) => ({ ...f, amc_required: String(e.target.value) }))
                  }
                  options={[
                    { value: 'no', label: 'No' },
                    { value: 'yes', label: 'Yes' },
                  ]}
                />
                {licenseForm.amc_required === 'yes' ? (
                  <FormField
                    label="AMC %"
                    type="number"
                    value={licenseForm.amc_percent}
                    onChange={(e) =>
                      setLicenseForm((f) => ({ ...f, amc_percent: e.target.value }))
                    }
                  />
                ) : null}
              </>
            )}
            <FormField
              label="Notes"
              multiline
              minRows={2}
              value={licenseForm.notes}
              onChange={(e) => setLicenseForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <FormDrawer
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign license"
        formId="it-software-assign-form"
        submitLabel="Assign"
        loading={assignMutation.isPending}
      >
        <Box
          component="form"
          id="it-software-assign-form"
          onSubmit={handleAssignSubmit}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Assignment">
            <FormSelect
              label="License pool"
              required
              value={assignForm.license_pool_id}
              onChange={(e) =>
                setAssignForm((f) => ({ ...f, license_pool_id: String(e.target.value) }))
              }
              options={licenseOptions}
            />
            <FormSelect
              label="User"
              required
              searchable
              value={assignForm.user_id}
              onChange={(e) => setAssignForm((f) => ({ ...f, user_id: String(e.target.value) }))}
              options={userOptions}
            />
            <FormField
              label="Notes"
              multiline
              minRows={2}
              value={assignForm.notes}
              onChange={(e) => setAssignForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <FormDrawer
        open={requirementOpen}
        onClose={() => setRequirementOpen(false)}
        title="Add software requirement"
        formId="it-software-requirement-form"
        submitLabel="Save"
        loading={requirementMutation.isPending}
      >
        <Box
          component="form"
          id="it-software-requirement-form"
          onSubmit={handleRequirementSubmit}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Requirement">
            <FormSelect
              label="Employee"
              required
              searchable
              value={requirementForm.user_id}
              onChange={(e) =>
                setRequirementForm((f) => ({ ...f, user_id: String(e.target.value) }))
              }
              options={userOptions}
            />
            <FormSelect
              label="Software"
              required
              value={requirementForm.software_id}
              onChange={(e) =>
                setRequirementForm((f) => ({ ...f, software_id: String(e.target.value) }))
              }
              options={softwareOptions}
            />
            <FormSelect
              label="Level"
              value={requirementForm.requirement_level}
              onChange={(e) =>
                setRequirementForm((f) => ({
                  ...f,
                  requirement_level: String(e.target.value),
                }))
              }
              options={[
                { value: 'required', label: 'Required' },
                { value: 'optional', label: 'Optional' },
              ]}
            />
            <FormField
              label="Version"
              value={requirementForm.version}
              onChange={(e) => setRequirementForm((f) => ({ ...f, version: e.target.value }))}
            />
            <FormField
              label="Reason"
              value={requirementForm.reason}
              onChange={(e) => setRequirementForm((f) => ({ ...f, reason: e.target.value }))}
            />
            <FormField
              label="Notes"
              multiline
              minRows={2}
              value={requirementForm.notes}
              onChange={(e) => setRequirementForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <FormDrawer
        open={Boolean(terminateTarget)}
        onClose={() => setTerminateTarget(null)}
        title="Terminate license"
        formId="it-software-terminate-form"
        submitLabel="Terminate license"
        loading={terminateMutation.isPending}
      >
        <Box
          component="form"
          id="it-software-terminate-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            terminateMutation.mutate();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Confirmation">
            <Typography variant="body2" color="text.secondary">
              {terminateTarget?.entitlement_code || terminateTarget?.software_name} will stop
              future assignment, renewal alerts, and forecast costs. Historical assignments and
              Finance history stay intact.
            </Typography>
            <FormField
              label="Reason"
              required
              value={terminateReason}
              onChange={(e) => setTerminateReason(e.target.value)}
            />
          </FormSection>
        </Box>
      </FormDrawer>

      <FormDrawer
        open={Boolean(renewTarget)}
        onClose={() => setRenewTarget(null)}
        title="Renew subscription"
        formId="it-software-renew-form"
        submitLabel="Confirm renewal"
        loading={renewMutation.isPending}
      >
        <Box
          component="form"
          id="it-software-renew-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            renewMutation.mutate();
          }}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}
        >
          <FormSection title="Renewal">
            <Typography variant="body2" color="text.secondary">
              {renewTarget?.entitlement_code || renewTarget?.software_name} — extends the
              entitlement period and records renewal history (does not overwrite prior renewals).
            </Typography>
            <FormField
              label="Renewal amount"
              type="number"
              value={renewAmount}
              onChange={(e) => setRenewAmount(e.target.value)}
            />
            <FormField
              label="New period end (optional)"
              type="date"
              value={renewPeriodEnd}
              onChange={(e) => setRenewPeriodEnd(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </FormSection>
        </Box>
      </FormDrawer>
    </PageContainer>
  );
}
