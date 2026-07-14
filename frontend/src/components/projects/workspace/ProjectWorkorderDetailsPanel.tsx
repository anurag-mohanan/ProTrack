import { useMemo, useRef, useState } from 'react';
import { Box, Grid, Stack, Typography } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import PrecisionManufacturingRoundedIcon from '@mui/icons-material/PrecisionManufacturingRounded';
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded';
import { FormField } from '../../ui/design-system';
import { ProsohmButton } from '../../ui/ProsohmButton';
import { useToast } from '../../../context/ToastContext';
import { commandCenterQueryKeys } from '../../../api/commandCenter';
import {
  extractWorkorderPdf,
  updateProject,
  type WorkorderPdfExtractResult,
} from '../../../services/projectService';
import type { Project } from '../../../types';
import { designTokens } from '../../../theme/designTokens';
import { formatCellValue, formatDisplayValue } from '../../../utils/format';
import { getErrorMessage } from '../../../api/client';

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

function applyExtractToForm(
  current: WorkorderFormState,
  extracted: WorkorderPdfExtractResult,
): WorkorderFormState {
  return {
    part_description: extracted.part_description?.trim() || current.part_description,
    work_order_number: extracted.work_order_number?.trim() || current.work_order_number,
    press_tonnage: extracted.press_tonnage?.trim() || current.press_tonnage,
    plastic_material: extracted.plastic_material?.trim() || current.plastic_material,
    cavity_count:
      extracted.cavity_count === null || extracted.cavity_count === undefined
        ? current.cavity_count
        : String(extracted.cavity_count),
    tool_type: extracted.tool_type?.trim() || current.tool_type,
    customer_specs: extracted.customer_specs?.trim() || current.customer_specs,
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
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<WorkorderFormState>(() => projectToForm(project));
  const [extractWarnings, setExtractWarnings] = useState<string[]>([]);

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
      setExtractWarnings([]);
      void queryClient.invalidateQueries({ queryKey: commandCenterQueryKeys.detail(project.id) });
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (error: Error) => showError(error.message),
  });

  const extractMutation = useMutation({
    mutationFn: (file: File) => extractWorkorderPdf(project.id, file),
    onSuccess: (extracted) => {
      setForm((current) => applyExtractToForm(current, extracted));
      setExtractWarnings(extracted.warnings ?? []);
      setEditing(true);
      const filled = [
        extracted.work_order_number,
        extracted.press_tonnage,
        extracted.plastic_material,
        extracted.cavity_count,
        extracted.tool_type,
        extracted.part_description,
        extracted.customer_specs,
      ].filter((value) => value !== null && value !== undefined && String(value).trim() !== '');
      if (filled.length) {
        showSuccess(`Imported ${filled.length} field${filled.length === 1 ? '' : 's'} from PDF — review and Save`);
      } else {
        showError('No workorder fields matched. Enter details manually or try another PDF.');
      }
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
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

  const onPickPdf = (file: File | null) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showError('Only PDF workorder files are supported.');
      return;
    }
    extractMutation.mutate(file);
  };

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
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0] ?? null;
          event.target.value = '';
          onPickPdf(file);
        }}
      />

      <Stack
        direction="row"
        spacing={1}
        sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.25, flexWrap: 'wrap' }}
      >
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <PrecisionManufacturingRoundedIcon color="primary" fontSize="small" />
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Workorder / tooling details
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Import a customer workorder PDF to autofill, then review and Save. Formats vary by customer.
            </Typography>
          </Box>
        </Box>
        {canEdit ? (
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
            <ProsohmButton
              buttonVariant="outlined"
              size="small"
              startIcon={<UploadFileRoundedIcon />}
              onClick={() => fileInputRef.current?.click()}
              loading={extractMutation.isPending}
              disabled={saveMutation.isPending}
            >
              Import workorder PDF
            </ProsohmButton>
            {editing ? (
              <>
                <ProsohmButton
                  buttonVariant="outlined"
                  size="small"
                  onClick={() => {
                    setForm(projectToForm(project));
                    setExtractWarnings([]);
                    setEditing(false);
                  }}
                  disabled={saveMutation.isPending || extractMutation.isPending}
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
              </>
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
            )}
          </Stack>
        ) : null}
      </Stack>

      {extractWarnings.length ? (
        <Typography variant="caption" color="warning.main" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
          {extractWarnings.join(' ')}
        </Typography>
      ) : null}

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
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <FormField
              label="Plastic material"
              value={form.plastic_material}
              onChange={(event) => setForm({ ...form, plastic_material: event.target.value })}
              maxLength={150}
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
                No workorder metadata yet. Import a PDF or edit details so completed tools stay searchable.
              </Typography>
            </Grid>
          ) : null}
        </Grid>
      )}
    </Box>
  );
}
