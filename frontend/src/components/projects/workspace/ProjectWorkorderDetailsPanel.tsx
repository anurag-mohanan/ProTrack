import { useMemo, useState } from 'react';
import { Box, Grid, Stack, Typography } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import PrecisionManufacturingRoundedIcon from '@mui/icons-material/PrecisionManufacturingRounded';
import { FormField } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { useToast } from '../../../context/ToastContext';
import { commandCenterQueryKeys } from '../../../api/commandCenter';
import { updateProject } from '../../../services/projectService';
import type { Project } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { formatCellValue, formatDisplayValue } from '../../../utils/format';

interface ProjectWorkorderDetailsPanelProps {
  project: Project;
  canEdit: boolean;
}

interface WorkorderFormState {
  work_order_number: string;
  press_tonnage: string;
  plastic_material: string;
  cavity_count: string;
  tool_type: string;
  customer_specs: string;
  part_description: string;
}

function projectToForm(project: Project): WorkorderFormState {
  return {
    work_order_number: project.work_order_number ?? '',
    press_tonnage: project.press_tonnage ?? '',
    plastic_material: project.plastic_material ?? '',
    cavity_count:
      project.cavity_count === null || project.cavity_count === undefined
        ? ''
        : String(project.cavity_count),
    tool_type: project.tool_type ?? '',
    customer_specs: project.customer_specs ?? '',
    part_description: project.part_description ?? '',
  };
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600, whiteSpace: 'pre-wrap' }}>
        {value || '—'}
      </Typography>
    </Box>
  );
}

export function ProjectWorkorderDetailsPanel({
  project,
  canEdit,
}: ProjectWorkorderDetailsPanelProps) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<WorkorderFormState>(() => projectToForm(project));

  const saveMutation = useMutation({
    mutationFn: () => {
      const cavityRaw = form.cavity_count.trim();
      const cavity =
        cavityRaw === ''
          ? null
          : Number.isFinite(Number(cavityRaw))
            ? Math.max(0, Math.trunc(Number(cavityRaw)))
            : null;
      return updateProject(project.id, {
        part_description: form.part_description.trim() || project.part_description,
        work_order_number: form.work_order_number.trim() || null,
        press_tonnage: form.press_tonnage.trim() || null,
        plastic_material: form.plastic_material.trim() || null,
        cavity_count: cavity,
        tool_type: form.tool_type.trim() || null,
        customer_specs: form.customer_specs.trim() || null,
      });
    },
    onSuccess: () => {
      showSuccess('Project details saved');
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: commandCenterQueryKeys.detail(project.id) });
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const hasAnyDetail = useMemo(
    () =>
      Boolean(
        project.work_order_number ||
          project.press_tonnage ||
          project.plastic_material ||
          project.cavity_count != null ||
          project.tool_type ||
          project.customer_specs,
      ),
    [project],
  );

  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 2,
        bgcolor: designTokens.semantic.card,
        p: 1.5,
      }}
    >
      <Stack
        direction="row"
        spacing={1}
        sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.25 }}
      >
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <PrecisionManufacturingRoundedIcon color="primary" fontSize="small" />
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Workorder / tooling details
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Searchable attributes from the customer workorder (manual entry for RC5; PDF extract later).
            </Typography>
          </Box>
        </Box>
        {canEdit ? (
          editing ? (
            <Stack direction="row" spacing={1}>
              <ProsohmButton
                buttonVariant="outlined"
                size="small"
                onClick={() => {
                  setForm(projectToForm(project));
                  setEditing(false);
                }}
                disabled={saveMutation.isPending}
              >
                Cancel
              </ProsohmButton>
              <ProsohmButton
                buttonVariant="primary"
                size="small"
                onClick={() => saveMutation.mutate()}
                loading={saveMutation.isPending}
              >
                Save
              </ProsohmButton>
            </Stack>
          ) : (
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              onClick={() => {
                setForm(projectToForm(project));
                setEditing(true);
              }}
            >
              Edit details
            </ProsohmButton>
          )
        ) : null}
      </Stack>

      {editing ? (
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Part description"
              value={form.part_description}
              onChange={(event) => setForm({ ...form, part_description: event.target.value })}
              maxLength={255}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Work order number"
              value={form.work_order_number}
              onChange={(event) => setForm({ ...form, work_order_number: event.target.value })}
              maxLength={100}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Press tonnage"
              value={form.press_tonnage}
              onChange={(event) => setForm({ ...form, press_tonnage: event.target.value })}
              maxLength={50}
              placeholder="e.g. 650T"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Plastic material"
              value={form.plastic_material}
              onChange={(event) => setForm({ ...form, plastic_material: event.target.value })}
              maxLength={150}
              placeholder="e.g. PP GF30"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <FormField
              label="Cavity count"
              type="number"
              value={form.cavity_count}
              onChange={(event) => setForm({ ...form, cavity_count: event.target.value })}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <FormField
              label="Tool type"
              value={form.tool_type}
              onChange={(event) => setForm({ ...form, tool_type: event.target.value })}
              maxLength={100}
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormField
              label="Customer specs / other details"
              multiline
              rows={3}
              value={form.customer_specs}
              onChange={(event) => setForm({ ...form, customer_specs: event.target.value })}
              maxLength={4000}
            />
          </Grid>
        </Grid>
      ) : (
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12 }}>
            <DetailItem label="Part description" value={formatDisplayValue(project.part_description)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <DetailItem label="Work order number" value={formatCellValue(project.work_order_number)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <DetailItem label="Press tonnage" value={formatCellValue(project.press_tonnage)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <DetailItem label="Plastic material" value={formatCellValue(project.plastic_material)} />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <DetailItem
              label="Cavity count"
              value={
                project.cavity_count === null || project.cavity_count === undefined
                  ? ''
                  : String(project.cavity_count)
              }
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <DetailItem label="Tool type" value={formatCellValue(project.tool_type)} />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <DetailItem label="Customer specs" value={formatCellValue(project.customer_specs)} />
          </Grid>
          {!hasAnyDetail ? (
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary">
                No workorder metadata yet. Capture tonnage, material, and specs so completed tools stay
                searchable.
              </Typography>
            </Grid>
          ) : null}
        </Grid>
      )}
    </Box>
  );
}
