import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { hireWithIt, fetchComputerTypes, itProvisioningKeys } from '../../api/itProvisioning';
import { fetchSoftwareCatalog, itOperationsKeys } from '../../api/itOperations';
import { fetchShifts } from '../../api/resourceShifts';
import { getErrorMessage } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { FormField, FormSelect } from '../ui/design-system';
import { ProsohmButton } from '../ui/ProsohmButton';
import type { Role } from '../../types';

const STEPS = ['Employee Details', 'Work Schedule', 'IT / Hardware', 'Software', 'Review & Submit'];

type SoftwareLine = {
  software_id: string;
  license_required: boolean;
  purpose: string;
  requirement_level: 'required' | 'optional';
};

type Props = {
  open: boolean;
  onClose: () => void;
  roles: Role[];
  defaultRoleId?: string;
};

const emptySoftware = (): SoftwareLine => ({
  software_id: '',
  license_required: true,
  purpose: '',
  requirement_level: 'required',
});

export function HireEmployeeWizard({ open, onClose, roles, defaultRoleId }: Props) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    designation: '',
    role_id: defaultRoleId || '',
    joining_date: '',
    employment_type: 'full_time',
    password: 'ChangeMe123!',
    shift_id: '',
    computer_required: true,
    computer_type: 'ENG_WS',
    monitor_quantity: 2,
    mouse_3d_required: false,
    wireless_mouse_required: false,
    priority: 'medium',
    notes: '',
  });
  const [software, setSoftware] = useState<SoftwareLine[]>([emptySoftware()]);

  const computerTypesQuery = useQuery({
    queryKey: itProvisioningKeys.computerTypes(),
    queryFn: fetchComputerTypes,
    enabled: open,
  });
  const shiftsQuery = useQuery({
    queryKey: ['resource-shifts', 'list', { active_only: true }],
    queryFn: () => fetchShifts({ active_only: true }),
    enabled: open,
  });
  const softwareQuery = useQuery({
    queryKey: itOperationsKeys.software({ active_only: true }),
    queryFn: () => fetchSoftwareCatalog({ active_only: true }),
    enabled: open,
  });

  const isLaptop = form.computer_type.includes('LAPTOP');
  const computerTypes = computerTypesQuery.data ?? [];
  const shifts = shiftsQuery.data ?? [];
  const catalog = softwareQuery.data ?? [];

  const hireMutation = useMutation({
    mutationFn: () =>
      hireWithIt({
        user: {
          first_name: form.first_name,
          last_name: form.last_name,
          email: form.email,
          phone: form.phone || null,
          designation: form.designation || null,
          role_id: form.role_id,
          joining_date: form.joining_date || null,
          employment_type: form.employment_type || null,
          password: form.password,
          must_change_password: true,
          is_active: true,
        },
        shift_id: form.shift_id || null,
        hardware: {
          computer_required: form.computer_required,
          computer_type: form.computer_required ? form.computer_type : null,
          monitor_quantity: form.computer_required ? form.monitor_quantity : 0,
          mouse_3d_required: form.mouse_3d_required,
          mouse_3d_is_required: form.mouse_3d_required,
          wireless_mouse_required: isLaptop ? form.wireless_mouse_required : false,
        },
        software: software
          .filter((row) => row.software_id)
          .map((row) => ({
            software_id: row.software_id,
            license_required: row.license_required,
            purpose: row.purpose || null,
            requirement_level: row.requirement_level,
          })),
        required_by: form.joining_date || null,
        priority: form.priority,
        notes: form.notes || null,
        create_checklist: true,
      }),
    onSuccess: (result) => {
      showSuccess(
        `Employee created. IT request ${result.provisioning.ticket_number || result.provisioning.id} opened.`,
      );
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      void queryClient.invalidateQueries({ queryKey: itProvisioningKeys.all });
      handleClose();
    },
    onError: (error) => showError(getErrorMessage(error)),
  });

  const canNext = useMemo(() => {
    if (step === 0) {
      return Boolean(form.first_name && form.last_name && form.email && form.role_id);
    }
    if (step === 1) return Boolean(form.shift_id);
    if (step === 2) {
      if (!form.computer_required) return true;
      return Boolean(form.computer_type);
    }
    return true;
  }, [step, form]);

  const handleClose = () => {
    setStep(0);
    onClose();
  };

  const setSoftwareLine = (index: number, patch: Partial<SoftwareLine>) => {
    setSoftware((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md">
      <DialogTitle>Add Employee</DialogTitle>
      <DialogContent>
        <Stepper activeStep={step} alternativeLabel sx={{ mb: 3, mt: 1 }}>
          {STEPS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {step === 0 ? (
          <Stack spacing={1.5}>
            <FormField
              label="First name"
              value={form.first_name}
              onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
              required
            />
            <FormField
              label="Last name"
              value={form.last_name}
              onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
              required
            />
            <FormField
              label="Email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required
            />
            <FormField
              label="Phone"
              value={form.phone}
              onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
            />
            <FormField
              label="Designation"
              value={form.designation}
              onChange={(e) => setForm((f) => ({ ...f, designation: e.target.value }))}
            />
            <FormSelect
              label="Role"
              value={form.role_id}
              options={roles.map((role) => ({ value: role.id, label: role.name }))}
              onChange={(e) => setForm((f) => ({ ...f, role_id: String(e.target.value) }))}
              required
            />
            <FormField
              label="Joining date"
              type="date"
              value={form.joining_date}
              onChange={(e) => setForm((f) => ({ ...f, joining_date: e.target.value }))}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormSelect
              label="Employment type"
              value={form.employment_type}
              options={[
                { value: 'full_time', label: 'Full time' },
                { value: 'part_time', label: 'Part time' },
                { value: 'contract', label: 'Contract' },
                { value: 'intern', label: 'Intern' },
              ]}
              onChange={(e) => setForm((f) => ({ ...f, employment_type: String(e.target.value) }))}
            />
          </Stack>
        ) : null}

        {step === 1 ? (
          <Stack spacing={1.5}>
            <FormSelect
              label="Shift"
              value={form.shift_id}
              options={(Array.isArray(shifts) ? shifts : []).map(
                (shift: { id: string; name: string; start_time?: string; end_time?: string }) => ({
                  value: shift.id,
                  label:
                    shift.start_time && shift.end_time
                      ? `${shift.name} (${shift.start_time}–${shift.end_time})`
                      : shift.name,
                }),
              )}
              onChange={(e) => setForm((f) => ({ ...f, shift_id: String(e.target.value) }))}
              required
            />
            <Typography variant="body2" color="text.secondary">
              Uses the company Shift master (First / Second / General).
            </Typography>
          </Stack>
        ) : null}

        {step === 2 ? (
          <Stack spacing={1.5}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.computer_required}
                  onChange={(e) => setForm((f) => ({ ...f, computer_required: e.target.checked }))}
                />
              }
              label="Computer required"
            />
            {form.computer_required ? (
              <>
                <FormSelect
                  label="Computer type"
                  value={form.computer_type}
                  options={computerTypes.map((row) => ({ value: row.code, label: row.label }))}
                  onChange={(e) => {
                    const code = String(e.target.value);
                    setForm((f) => ({
                      ...f,
                      computer_type: code,
                      monitor_quantity: code === 'ENG_WS' ? 2 : code.includes('LAPTOP') ? 0 : 1,
                      wireless_mouse_required: code.includes('LAPTOP'),
                    }));
                  }}
                />
                <FormSelect
                  label="Number of monitors"
                  value={String(form.monitor_quantity)}
                  options={[0, 1, 2, 3, 4].map((n) => ({ value: String(n), label: String(n) }))}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, monitor_quantity: Number(e.target.value) }))
                  }
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={form.mouse_3d_required}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, mouse_3d_required: e.target.checked }))
                      }
                    />
                  }
                  label="3D mouse required"
                />
                {isLaptop ? (
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={form.wireless_mouse_required}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, wireless_mouse_required: e.target.checked }))
                        }
                      />
                    }
                    label="Wireless mouse required"
                  />
                ) : null}
              </>
            ) : null}
            <Alert severity="info">
              This captures requirements only. IT assigns actual assets later.
            </Alert>
          </Stack>
        ) : null}

        {step === 3 ? (
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Up to 5 software items from the Software master (onboarding limit).
            </Typography>
            {software.map((row, index) => (
              <Box
                key={index}
                sx={{ border: '1px solid', borderColor: 'divider', p: 1.5, borderRadius: 1 }}
              >
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Software #{index + 1}
                </Typography>
                <Stack spacing={1}>
                  <FormSelect
                    label="Software"
                    value={row.software_id}
                    options={[
                      { value: '', label: '—' },
                      ...catalog.map((item: { id: string; name: string }) => ({
                        value: item.id,
                        label: item.name,
                      })),
                    ]}
                    onChange={(e) => setSoftwareLine(index, { software_id: String(e.target.value) })}
                  />
                  <FormField
                    label="Purpose / requirement"
                    value={row.purpose}
                    onChange={(e) => setSoftwareLine(index, { purpose: e.target.value })}
                  />
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={row.license_required}
                        onChange={(e) =>
                          setSoftwareLine(index, { license_required: e.target.checked })
                        }
                      />
                    }
                    label="License required"
                  />
                  <FormSelect
                    label="Required / optional"
                    value={row.requirement_level}
                    options={[
                      { value: 'required', label: 'Required' },
                      { value: 'optional', label: 'Optional' },
                    ]}
                    onChange={(e) =>
                      setSoftwareLine(index, {
                        requirement_level: e.target.value as 'required' | 'optional',
                      })
                    }
                  />
                </Stack>
              </Box>
            ))}
            <Stack direction="row" spacing={1}>
              <ProsohmButton
                buttonVariant="secondary"
                disabled={software.length >= 5}
                onClick={() => setSoftware((prev) => [...prev, emptySoftware()])}
              >
                Add software
              </ProsohmButton>
              {software.length > 1 ? (
                <ProsohmButton
                  buttonVariant="secondary"
                  onClick={() => setSoftware((prev) => prev.slice(0, -1))}
                >
                  Remove last
                </ProsohmButton>
              ) : null}
            </Stack>
          </Stack>
        ) : null}

        {step === 4 ? (
          <Stack spacing={1}>
            <Typography>
              <strong>
                {form.first_name} {form.last_name}
              </strong>{' '}
              · {form.email}
            </Typography>
            <Typography variant="body2">Joining: {form.joining_date || '—'}</Typography>
            <Typography variant="body2">
              Computer:{' '}
              {form.computer_required
                ? `${computerTypes.find((c) => c.code === form.computer_type)?.label || form.computer_type}, ${form.monitor_quantity} monitor(s)${form.mouse_3d_required ? ', 3D mouse' : ''}`
                : 'Not required'}
            </Typography>
            <Typography variant="body2">
              Software:{' '}
              {software.filter((s) => s.software_id).length
                ? software
                    .filter((s) => s.software_id)
                    .map(
                      (s) =>
                        catalog.find((c: { id: string }) => c.id === s.software_id)?.name ||
                        s.software_id,
                    )
                    .join(', ')
                : 'None'}
            </Typography>
            <Alert severity="success">
              Submitting creates the employee account and an IT provisioning request automatically.
            </Alert>
          </Stack>
        ) : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <ProsohmButton buttonVariant="secondary" onClick={handleClose}>
          Cancel
        </ProsohmButton>
        {step > 0 ? (
          <ProsohmButton buttonVariant="secondary" onClick={() => setStep((s) => s - 1)}>
            Back
          </ProsohmButton>
        ) : null}
        {step < STEPS.length - 1 ? (
          <ProsohmButton
            buttonVariant="primary"
            disabled={!canNext}
            onClick={() => setStep((s) => s + 1)}
          >
            Next
          </ProsohmButton>
        ) : (
          <ProsohmButton
            buttonVariant="primary"
            disabled={hireMutation.isPending}
            onClick={() => hireMutation.mutate()}
          >
            {hireMutation.isPending ? 'Submitting…' : 'Submit'}
          </ProsohmButton>
        )}
      </DialogActions>
    </Dialog>
  );
}
