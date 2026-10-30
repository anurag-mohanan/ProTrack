import { useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '../../api/client';
import {
  addSkillRelationship,
  createSkill,
  fetchSkillTaxonomy,
  loadStandardPack,
  removeSkillRelationship,
  renameSkillCategory,
  skillQueryKeys,
  updateProficiencyLevel,
  updateSkill,
  type StandardPackResult,
} from '../../api/skills';
import { useToast } from '../../context/ToastContext';
import type { SkSkill, SkSkillWrite } from '../../types/Skills';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FilterSelect } from '../ui/design-system/FilterSelect';

const EMPTY: SkSkillWrite = {
  name: '',
  category: null,
  kind: null,
  description: null,
  aliases: [],
  discipline_id: null,
  customer_id: null,
  is_critical: false,
  min_verified_coverage: null,
  specialist_level: null,
  reassessment_months: null,
  sort_order: 0,
  is_active: true,
};

function toWrite(s: SkSkill): SkSkillWrite {
  return {
    name: s.name,
    category: s.category,
    kind: s.kind,
    description: s.description,
    aliases: s.aliases,
    discipline_id: s.discipline_id,
    customer_id: s.customer_id,
    is_critical: s.is_critical,
    min_verified_coverage: s.min_verified_coverage,
    specialist_level: s.specialist_level,
    reassessment_months: s.reassessment_months,
    sort_order: s.sort_order,
    is_active: s.is_active,
  };
}

const intOrNull = (v: string) => (v === '' ? null : Number(v));

export function SkillTaxonomyPanel() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const taxonomyQuery = useQuery({ queryKey: skillQueryKeys.taxonomy(true), queryFn: () => fetchSkillTaxonomy(true) });
  const [editing, setEditing] = useState<{ id: string | null; body: SkSkillWrite } | null>(null);
  const [aliasText, setAliasText] = useState('');
  const [renameFrom, setRenameFrom] = useState('');
  const [renameTo, setRenameTo] = useState('');
  const [rel, setRel] = useState({ from: '', to: '', type: 'related' });
  const [levelEdits, setLevelEdits] = useState<Record<number, { name: string; description: string }>>({});
  const [pack, setPack] = useState<StandardPackResult | null>(null);

  const refresh = () => void queryClient.invalidateQueries({ queryKey: skillQueryKeys.all });
  const onError = (err: unknown) => showError(getErrorMessage(err));
  const run = useMutation({
    mutationFn: async (fn: () => Promise<string | void>) => fn(),
    onSuccess: (message) => {
      if (message) showSuccess(message);
      refresh();
    },
    onError,
  });

  if (taxonomyQuery.isLoading) return <LoadingState message="Loading taxonomy…" />;
  if (taxonomyQuery.error) return <ErrorState error={taxonomyQuery.error} />;
  const t = taxonomyQuery.data!;

  const openEditor = (skill: SkSkill | null) => {
    const body = skill ? toWrite(skill) : { ...EMPTY };
    setEditing({ id: skill?.id ?? null, body });
    setAliasText(body.aliases.join(', '));
  };
  const saveSkill = () => {
    if (!editing) return;
    const body = { ...editing.body, aliases: aliasText.split(',').map((a) => a.trim()).filter(Boolean) };
    run.mutate(async () => {
      if (editing.id) await updateSkill(editing.id, body);
      else await createSkill(body);
      setEditing(null);
      return editing.id ? 'Skill updated' : 'Skill added';
    });
  };
  const set = (patch: Partial<SkSkillWrite>) => setEditing((e) => (e ? { ...e, body: { ...e.body, ...patch } } : e));

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        Names are checked for duplicates ignoring case, spacing and punctuation, and against aliases. Renaming keeps the
        old name as an alias. Deactivated skills stay on existing records but cannot be newly declared.
      </Alert>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1">Skills ({t.skills.length})</Typography>
          <Button variant="contained" size="small" onClick={() => openEditor(null)}>
            Add skill
          </Button>
        </Stack>
        <TableContainer sx={{ maxHeight: 520 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Skill</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Aliases</TableCell>
                <TableCell>Critical</TableCell>
                <TableCell align="right">Holders</TableCell>
                <TableCell>Status</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {t.skills.map((s) => (
                <TableRow key={s.id} hover sx={{ opacity: s.is_active ? 1 : 0.55 }}>
                  <TableCell>{s.name}</TableCell>
                  <TableCell>{s.category ?? '—'}</TableCell>
                  <TableCell>{s.kind_label ?? '—'}</TableCell>
                  <TableCell>{s.aliases.join(', ') || '—'}</TableCell>
                  <TableCell>
                    {s.is_critical ? <Chip size="small" color="error" label={s.min_verified_coverage ? `Target ${s.min_verified_coverage}` : 'Yes'} /> : '—'}
                  </TableCell>
                  <TableCell align="right">{s.holder_count}</TableCell>
                  <TableCell>{s.is_active ? 'Active' : 'Inactive'}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => openEditor(s)}>
                      Edit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2}>
        <Paper variant="outlined" sx={{ p: 2, flex: 1 }}>
          <Typography variant="subtitle1" gutterBottom>
            Rename a category
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <FilterSelect label="Category" value={renameFrom} onChange={(e) => setRenameFrom(e.target.value)}>
              <MenuItem value="">Select</MenuItem>
              {t.categories.map((c) => (
                <MenuItem key={c} value={c}>
                  {c}
                </MenuItem>
              ))}
            </FilterSelect>
            <TextField size="small" label="New name" value={renameTo} onChange={(e) => setRenameTo(e.target.value)} fullWidth />
            <Button
              variant="outlined"
              disabled={!renameFrom || !renameTo.trim() || run.isPending}
              onClick={() =>
                run.mutate(async () => {
                  const { updated } = await renameSkillCategory(renameFrom, renameTo.trim());
                  setRenameFrom('');
                  setRenameTo('');
                  return `${updated} skill(s) moved`;
                })
              }
            >
              Rename
            </Button>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, flex: 1 }}>
          <Typography variant="subtitle1" gutterBottom>
            Standard engineering taxonomy
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            CAD software, mold design, surfacing, fixtures and tooling, and documentation skills. Only missing skills are
            added; existing ones (including aliases such as NX for Siemens NX) are reused.
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button variant="outlined" disabled={run.isPending} onClick={() => run.mutate(async () => setPack(await loadStandardPack(true)))}>
              Preview
            </Button>
            <Button
              variant="contained"
              disabled={!pack || !pack.created.length || run.isPending}
              onClick={() =>
                run.mutate(async () => {
                  const result = await loadStandardPack(false);
                  setPack(result);
                  return `${result.created.length} skill(s) added`;
                })
              }
            >
              Add missing skills
            </Button>
          </Stack>
          {pack ? (
            <Typography variant="body2" sx={{ mt: 1 }}>
              {pack.dry_run ? 'Would add' : 'Added'} {pack.created.length}: {pack.created.map((c) => c.name).join(', ') || 'nothing'}.{' '}
              Already present: {pack.already_present.map((p) => (p.existing_name === p.name ? p.name : `${p.name} → ${p.existing_name}`)).join(', ') || 'none'}.
            </Typography>
          ) : null}
        </Paper>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Relationships
        </Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ mb: 1.5 }}>
          <FilterSelect label="Skill" value={rel.from} onChange={(e) => setRel({ ...rel, from: e.target.value })}>
            <MenuItem value="">Select</MenuItem>
            {t.skills.filter((s) => s.is_active).map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect label="Relationship" value={rel.type} onChange={(e) => setRel({ ...rel, type: e.target.value })}>
            {t.relation_types.map((r) => (
              <MenuItem key={r.value} value={r.value}>
                {r.label}
              </MenuItem>
            ))}
          </FilterSelect>
          <FilterSelect label="Related skill" value={rel.to} onChange={(e) => setRel({ ...rel, to: e.target.value })}>
            <MenuItem value="">Select</MenuItem>
            {t.skills.filter((s) => s.is_active && s.id !== rel.from).map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </FilterSelect>
          <Button
            variant="outlined"
            disabled={!rel.from || !rel.to || run.isPending}
            onClick={() =>
              run.mutate(async () => {
                await addSkillRelationship({ from_skill_id: rel.from, to_skill_id: rel.to, relation_type: rel.type, note: null });
                setRel({ from: '', to: '', type: rel.type });
                return 'Relationship added';
              })
            }
          >
            Add
          </Button>
        </Stack>
        {t.relationships.length ? (
          <Stack spacing={0.5}>
            {t.relationships.map((r) => (
              <Stack key={r.id} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Typography variant="body2">
                  {r.from_skill_name} — <em>{r.relation_label.toLowerCase()}</em> — {r.to_skill_name}
                </Typography>
                <IconButton size="small" onClick={() => run.mutate(async () => removeSkillRelationship(r.id))} aria-label="Remove relationship">
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </Stack>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No relationships yet.
          </Typography>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Proficiency levels
        </Typography>
        <Stack spacing={1}>
          {t.proficiency_levels.map((l) => {
            const edit = levelEdits[l.level] ?? { name: l.name, description: l.description ?? '' };
            const changed = edit.name !== l.name || edit.description !== (l.description ?? '');
            return (
              <Stack key={l.level} direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ alignItems: { md: 'center' } }}>
                <Typography variant="body2" sx={{ width: 24, fontWeight: 600 }}>
                  {l.level}
                </Typography>
                <TextField
                  size="small"
                  label="Name"
                  value={edit.name}
                  onChange={(e) => setLevelEdits({ ...levelEdits, [l.level]: { ...edit, name: e.target.value } })}
                  sx={{ width: 180 }}
                />
                <TextField
                  size="small"
                  label="Description"
                  value={edit.description}
                  onChange={(e) => setLevelEdits({ ...levelEdits, [l.level]: { ...edit, description: e.target.value } })}
                  fullWidth
                />
                <Button
                  size="small"
                  disabled={!changed || !edit.name.trim() || run.isPending}
                  onClick={() =>
                    run.mutate(async () => {
                      await updateProficiencyLevel(l.level, edit.name.trim(), edit.description.trim() || null);
                      return `Level ${l.level} updated`;
                    })
                  }
                >
                  Save
                </Button>
              </Stack>
            );
          })}
        </Stack>
      </Paper>

      <Dialog open={Boolean(editing)} onClose={() => setEditing(null)} maxWidth="md" fullWidth>
        <DialogTitle>{editing?.id ? 'Edit skill' : 'Add skill'}</DialogTitle>
        {editing ? (
          <DialogContent>
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                <TextField size="small" label="Name" value={editing.body.name} onChange={(e) => set({ name: e.target.value })} fullWidth required />
                <TextField
                  size="small"
                  label="Category"
                  value={editing.body.category ?? ''}
                  onChange={(e) => set({ category: e.target.value || null })}
                  fullWidth
                  helperText={t.categories.length ? `Existing: ${t.categories.join(', ')}` : undefined}
                />
              </Stack>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                <FilterSelect label="Type" value={editing.body.kind ?? ''} onChange={(e) => set({ kind: e.target.value || null })}>
                  <MenuItem value="">Not set</MenuItem>
                  {t.kinds.map((k) => (
                    <MenuItem key={k.value} value={k.value}>
                      {k.label}
                    </MenuItem>
                  ))}
                </FilterSelect>
                <FilterSelect label="Discipline" value={editing.body.discipline_id ?? ''} onChange={(e) => set({ discipline_id: e.target.value || null })}>
                  <MenuItem value="">Not set</MenuItem>
                  {t.disciplines.map((d) => (
                    <MenuItem key={d.id} value={d.id}>
                      {d.name}
                    </MenuItem>
                  ))}
                </FilterSelect>
              </Stack>
              <TextField size="small" label="Aliases (comma separated)" value={aliasText} onChange={(e) => setAliasText(e.target.value)} fullWidth />
              <TextField
                size="small"
                label="Description"
                value={editing.body.description ?? ''}
                onChange={(e) => set({ description: e.target.value || null })}
                fullWidth
                multiline
              />
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ alignItems: { md: 'center' } }}>
                <FormControlLabel
                  control={<Checkbox checked={editing.body.is_critical} onChange={(e) => set({ is_critical: e.target.checked })} />}
                  label="Critical (management decision)"
                />
                <TextField
                  size="small"
                  type="number"
                  label="Verified coverage target"
                  value={editing.body.min_verified_coverage ?? ''}
                  onChange={(e) => set({ min_verified_coverage: intOrNull(e.target.value) })}
                  slotProps={{ htmlInput: { min: 1, max: 100 } }}
                  sx={{ width: 190 }}
                />
                <FilterSelect
                  label="Specialist level"
                  value={editing.body.specialist_level ? String(editing.body.specialist_level) : ''}
                  onChange={(e) => set({ specialist_level: intOrNull(e.target.value) })}
                  sx={{ width: 190 }}
                >
                  <MenuItem value="">Default (4)</MenuItem>
                  {t.proficiency_levels.map((l) => (
                    <MenuItem key={l.level} value={String(l.level)}>
                      {l.level} — {l.name}
                    </MenuItem>
                  ))}
                </FilterSelect>
                <TextField
                  size="small"
                  type="number"
                  label="Reassess every (months)"
                  value={editing.body.reassessment_months ?? ''}
                  onChange={(e) => set({ reassessment_months: intOrNull(e.target.value) })}
                  slotProps={{ htmlInput: { min: 1, max: 120 } }}
                  sx={{ width: 190 }}
                />
              </Stack>
              <FormControlLabel
                control={<Checkbox checked={editing.body.is_active} onChange={(e) => set({ is_active: e.target.checked })} />}
                label="Active"
              />
            </Stack>
          </DialogContent>
        ) : null}
        <DialogActions>
          <Button onClick={() => setEditing(null)}>Cancel</Button>
          <Button variant="contained" disabled={!editing?.body.name.trim() || run.isPending} onClick={saveSkill}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
