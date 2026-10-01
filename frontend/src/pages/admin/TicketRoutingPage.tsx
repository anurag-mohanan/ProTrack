import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import SupportAgentRoundedIcon from '@mui/icons-material/SupportAgentRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PageContainer } from '../../components/common/PageContainer';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';
import { getErrorMessage } from '../../api/client';
import { ticketsApi, usersApi } from '../../api/resources';
import { useTicketCatalog } from '../../components/tickets/useTicketMeta';
import type {
  TicketCategory,
  TicketCategoryRoute,
  TicketCategoryRouteUpdate,
  TicketPriority,
  TicketRoutingRule,
  TicketRoutingRuleWrite,
  TicketSlaPolicy,
} from '../../types/tickets';

type UserOption = { id: string; name: string };

function useUserOptions(): UserOption[] {
  const usersQuery = useQuery({
    queryKey: ['users', 'active-lite'],
    queryFn: () => usersApi.list({ limit: 500 }),
  });
  return useMemo(
    () =>
      (usersQuery.data ?? [])
        .filter((user) => user.is_active !== false)
        .map((user) => ({ id: user.id, name: `${user.first_name} ${user.last_name}`.trim() }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [usersQuery.data],
  );
}

function PersonSelect({
  label,
  value,
  users,
  emptyLabel,
  onChange,
}: {
  label: string;
  value: string | null;
  users: UserOption[];
  emptyLabel: string;
  onChange: (value: string | null) => void;
}) {
  return (
    <TextField
      select
      size="small"
      label={label}
      value={value ?? ''}
      onChange={(event) => onChange(event.target.value || null)}
      sx={{ minWidth: 200, flex: '1 1 200px' }}
    >
      <MenuItem value="">{emptyLabel}</MenuItem>
      {users.map((user) => (
        <MenuItem key={user.id} value={user.id}>
          {user.name}
        </MenuItem>
      ))}
    </TextField>
  );
}

function routeForm(route: TicketCategoryRoute): TicketCategoryRouteUpdate {
  return {
    assignee_user_id: route.assignee_user_id,
    backup_user_id: route.backup_user_id,
    escalation_user_id: route.escalation_user_id,
    org_department_id: route.org_department_id,
    is_active: route.is_active,
    effective_from: route.effective_from,
  };
}

function CategoryRouteCard({ route, users }: { route: TicketCategoryRoute; users: UserOption[] }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TicketCategoryRouteUpdate>(() => routeForm(route));
  const dirty = JSON.stringify(form) !== JSON.stringify(routeForm(route));
  const save = useMutation({
    mutationFn: () => ticketsApi.setRoute(route.category, form),
    onSuccess: (saved) => {
      showSuccess(`${saved.category_label} routing saved.`);
      void queryClient.invalidateQueries({ queryKey: ['ticket-routes'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });

  return (
    <ContentCard noPadding>
      <Box sx={{ px: 2, py: 1.5 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
          <SupportAgentRoundedIcon fontSize="small" color="primary" />
          <Typography sx={{ fontWeight: 800 }}>{route.category_label}</Typography>
          {!route.is_active ? <Chip size="small" label="Inactive" /> : null}
        </Stack>
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1.25 }}>
          {route.assignee_user_id
            ? `New tickets go to ${route.assignee_name ?? 'the primary owner'}; the backup takes them when the primary is inactive.`
            : 'No primary owner — tickets wait in the team queue and admins are told the ticket needs an owner.'}
          {!route.assignee_user_id && route.fallback_roles.length > 0
            ? ` Queue roles: ${route.fallback_roles.join(', ')}.`
            : ''}
        </Typography>
        <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1.25, alignItems: 'center' }}>
          <PersonSelect
            label="Primary owner"
            value={form.assignee_user_id ?? null}
            users={users}
            emptyLabel="— Team queue —"
            onChange={(value) => setForm((current) => ({ ...current, assignee_user_id: value }))}
          />
          <PersonSelect
            label="Backup"
            value={form.backup_user_id ?? null}
            users={users}
            emptyLabel="— None —"
            onChange={(value) => setForm((current) => ({ ...current, backup_user_id: value }))}
          />
          <PersonSelect
            label="Escalation contact"
            value={form.escalation_user_id ?? null}
            users={users}
            emptyLabel="— None —"
            onChange={(value) => setForm((current) => ({ ...current, escalation_user_id: value }))}
          />
          <TextField
            size="small"
            type="date"
            label="Effective from"
            value={form.effective_from ?? ''}
            onChange={(event) => setForm((current) => ({ ...current, effective_from: event.target.value || null }))}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 170 }}
          />
          <FormControlLabel
            control={
              <Checkbox
                size="small"
                checked={form.is_active ?? true}
                onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
              />
            }
            label={<Typography variant="body2">Active</Typography>}
          />
          <ProsohmButton
            size="small"
            buttonVariant="primary"
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate()}
          >
            Save
          </ProsohmButton>
        </Stack>
      </Box>
    </ContentCard>
  );
}

const EMPTY_RULE: TicketRoutingRuleWrite = {
  category: 'it',
  subcategory: null,
  source_module: null,
  primary_user_id: null,
  backup_user_id: null,
  escalation_user_id: null,
  default_priority: null,
  is_active: true,
  effective_from: null,
  notes: null,
};

function RuleDialog({
  rule,
  users,
  onClose,
}: {
  rule: TicketRoutingRule | 'new';
  users: UserOption[];
  onClose: () => void;
}) {
  const catalog = useTicketCatalog();
  const { showSuccess } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TicketRoutingRuleWrite>(() => {
    if (rule === 'new') return EMPTY_RULE;
    const { id: _id, primary_name: _p, backup_name: _b, escalation_name: _e, ...rest } = rule;
    void _id;
    void _p;
    void _b;
    void _e;
    return rest;
  });
  const save = useMutation({
    mutationFn: () => (rule === 'new' ? ticketsApi.createRule(form) : ticketsApi.updateRule(rule.id, form)),
    onSuccess: () => {
      showSuccess('Routing rule saved.');
      void queryClient.invalidateQueries({ queryKey: ['ticket-routing-rules'] });
      onClose();
    },
  });
  const subcategories = catalog.data?.subcategories[form.category] ?? {};

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{rule === 'new' ? 'New routing rule' : 'Edit routing rule'}</DialogTitle>
      <DialogContent>
        <Stack spacing={1.5} sx={{ pt: 0.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              select
              fullWidth
              size="small"
              label="Category"
              value={form.category}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  category: event.target.value as TicketCategory,
                  subcategory: null,
                }))
              }
            >
              {Object.entries(catalog.data?.categories ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              fullWidth
              size="small"
              label="Subcategory"
              value={form.subcategory ?? ''}
              onChange={(event) => setForm((current) => ({ ...current, subcategory: event.target.value || null }))}
            >
              <MenuItem value="">Any</MenuItem>
              {Object.entries(subcategories).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              select
              fullWidth
              size="small"
              label="Source"
              value={form.source_module ?? ''}
              onChange={(event) => setForm((current) => ({ ...current, source_module: event.target.value || null }))}
            >
              <MenuItem value="">Any source</MenuItem>
              {Object.entries(catalog.data?.sources ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              fullWidth
              size="small"
              label="Default priority"
              value={form.default_priority ?? ''}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  default_priority: (event.target.value || null) as TicketPriority | null,
                }))
              }
            >
              <MenuItem value="">Keep requested priority</MenuItem>
              {Object.entries(catalog.data?.priorities ?? {}).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1.25 }}>
            <PersonSelect
              label="Primary owner"
              value={form.primary_user_id}
              users={users}
              emptyLabel="— Category default —"
              onChange={(value) => setForm((current) => ({ ...current, primary_user_id: value }))}
            />
            <PersonSelect
              label="Backup"
              value={form.backup_user_id}
              users={users}
              emptyLabel="— None —"
              onChange={(value) => setForm((current) => ({ ...current, backup_user_id: value }))}
            />
            <PersonSelect
              label="Escalation contact"
              value={form.escalation_user_id}
              users={users}
              emptyLabel="— None —"
              onChange={(value) => setForm((current) => ({ ...current, escalation_user_id: value }))}
            />
          </Stack>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
            <TextField
              size="small"
              type="date"
              label="Effective from"
              value={form.effective_from ?? ''}
              onChange={(event) => setForm((current) => ({ ...current, effective_from: event.target.value || null }))}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={form.is_active}
                  onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
                />
              }
              label={<Typography variant="body2">Active</Typography>}
            />
          </Stack>
          <TextField
            size="small"
            label="Notes"
            multiline
            minRows={2}
            value={form.notes ?? ''}
            onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value || null }))}
          />
          <Typography variant="caption" color="text.secondary">
            The most specific active rule wins (subcategory and source before category). Rules are
            deactivated rather than deleted so routing history stays explainable.
          </Typography>
          {save.isError ? <Alert severity="error">{getErrorMessage(save.error)}</Alert> : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <ProsohmButton buttonVariant="secondary" onClick={onClose} disabled={save.isPending}>
          Cancel
        </ProsohmButton>
        <ProsohmButton buttonVariant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          Save rule
        </ProsohmButton>
      </DialogActions>
    </Dialog>
  );
}

function RoutingRulesTab({ users }: { users: UserOption[] }) {
  const catalog = useTicketCatalog();
  const rulesQuery = useQuery({ queryKey: ['ticket-routing-rules'], queryFn: ticketsApi.listRules });
  const [editing, setEditing] = useState<TicketRoutingRule | 'new' | null>(null);

  if (rulesQuery.isLoading) return <LoadingState message="Loading routing rules…" />;
  if (rulesQuery.isError) return <Alert severity="error">{getErrorMessage(rulesQuery.error)}</Alert>;
  const rules = rulesQuery.data ?? [];

  return (
    <ContentCard>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Route a subcategory or source to a specific owner, overriding the category owner.
        </Typography>
        <ProsohmButton size="small" buttonVariant="primary" startIcon={<AddIcon />} onClick={() => setEditing('new')}>
          New rule
        </ProsohmButton>
      </Stack>
      {rules.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
          No routing rules yet. Tickets use the category owners.
        </Typography>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Category</TableCell>
              <TableCell>Subcategory</TableCell>
              <TableCell>Source</TableCell>
              <TableCell>Primary</TableCell>
              <TableCell>Backup</TableCell>
              <TableCell>Escalation</TableCell>
              <TableCell>Status</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {rules.map((rule) => (
              <TableRow key={rule.id} hover sx={{ opacity: rule.is_active ? 1 : 0.6 }}>
                <TableCell>{catalog.data?.categories[rule.category] ?? rule.category}</TableCell>
                <TableCell>
                  {rule.subcategory ? catalog.data?.subcategories[rule.category]?.[rule.subcategory] ?? rule.subcategory : 'Any'}
                </TableCell>
                <TableCell>{rule.source_module ? catalog.data?.sources[rule.source_module] ?? rule.source_module : 'Any'}</TableCell>
                <TableCell>{rule.primary_name ?? '—'}</TableCell>
                <TableCell>{rule.backup_name ?? '—'}</TableCell>
                <TableCell>{rule.escalation_name ?? '—'}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={rule.is_active ? 'success' : 'default'}
                    label={rule.is_active ? 'Active' : 'Inactive'}
                  />
                </TableCell>
                <TableCell align="right">
                  <IconButton size="small" aria-label="Edit routing rule" onClick={() => setEditing(rule)}>
                    <EditOutlinedIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {editing ? <RuleDialog rule={editing} users={users} onClose={() => setEditing(null)} /> : null}
    </ContentCard>
  );
}

function numberOrNull(value: string): number | null {
  if (value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : null;
}

function SlaRow({ policy, categoryLabel, priorityLabel }: { policy: TicketSlaPolicy; categoryLabel: string; priorityLabel: string }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(policy);
  const dirty = JSON.stringify(form) !== JSON.stringify(policy);
  const save = useMutation({
    mutationFn: () => ticketsApi.saveSla(form),
    onSuccess: () => {
      showSuccess('SLA policy saved. It applies to tickets created from now on.');
      void queryClient.invalidateQueries({ queryKey: ['ticket-sla-policies'] });
    },
    onError: (error: unknown) => showError(getErrorMessage(error)),
  });
  const hoursField = (key: 'response_hours' | 'resolution_hours' | 'escalate_after_hours') => (
    <TextField
      size="small"
      type="number"
      value={form[key] ?? ''}
      onChange={(event) => setForm((current) => ({ ...current, [key]: numberOrNull(event.target.value) }))}
      sx={{ width: 100 }}
      slotProps={{ htmlInput: { min: 0, 'aria-label': `${categoryLabel} ${priorityLabel} ${key.replace(/_/g, ' ')}` } }}
    />
  );

  return (
    <TableRow hover>
      <TableCell>{categoryLabel}</TableCell>
      <TableCell>{priorityLabel}</TableCell>
      <TableCell>{hoursField('response_hours')}</TableCell>
      <TableCell>{hoursField('resolution_hours')}</TableCell>
      <TableCell>
        <TextField
          size="small"
          type="number"
          value={form.due_soon_hours}
          onChange={(event) => setForm((current) => ({ ...current, due_soon_hours: numberOrNull(event.target.value) ?? 0 }))}
          sx={{ width: 90 }}
          slotProps={{ htmlInput: { min: 0, 'aria-label': `${categoryLabel} ${priorityLabel} due soon hours` } }}
        />
      </TableCell>
      <TableCell>{hoursField('escalate_after_hours')}</TableCell>
      <TableCell>
        <Checkbox
          size="small"
          checked={form.is_active}
          onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
          slotProps={{ input: { 'aria-label': `${categoryLabel} ${priorityLabel} active` } }}
        />
      </TableCell>
      <TableCell align="right">
        <ProsohmButton size="small" buttonVariant="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          Save
        </ProsohmButton>
      </TableCell>
    </TableRow>
  );
}

function SlaTab() {
  const catalog = useTicketCatalog();
  const slaQuery = useQuery({ queryKey: ['ticket-sla-policies'], queryFn: ticketsApi.listSla });
  if (slaQuery.isLoading) return <LoadingState message="Loading SLA policies…" />;
  if (slaQuery.isError) return <Alert severity="error">{getErrorMessage(slaQuery.error)}</Alert>;

  return (
    <ContentCard>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Hours are counted from ticket creation. Owners are alerted once when a ticket is due soon and
        once when it becomes overdue; the escalation contact is alerted once after the escalation time.
        &ldquo;All categories&rdquo; applies where no category-specific policy exists.
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Category</TableCell>
            <TableCell>Priority</TableCell>
            <TableCell>First response (h)</TableCell>
            <TableCell>Resolution (h)</TableCell>
            <TableCell>Due-soon window (h)</TableCell>
            <TableCell>Escalate after (h)</TableCell>
            <TableCell>Active</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {(slaQuery.data ?? []).map((policy) => (
            <SlaRow
              key={`${policy.category}-${policy.priority}-${policy.id ?? ''}`}
              policy={policy}
              categoryLabel={policy.category === '*' ? 'All categories' : catalog.data?.categories[policy.category] ?? policy.category}
              priorityLabel={catalog.data?.priorities[policy.priority] ?? policy.priority}
            />
          ))}
        </TableBody>
      </Table>
    </ContentCard>
  );
}

export default function TicketRoutingPage() {
  const [tab, setTab] = useState<'owners' | 'rules' | 'sla'>('owners');
  const users = useUserOptions();
  const routesQuery = useQuery({ queryKey: ['ticket-routes'], queryFn: () => ticketsApi.listRoutes() });

  return (
    <PageContainer>
      <PageHeader
        title="Help Desk Routing"
        subtitle="Choose who owns each ticket category, with a backup and an escalation contact, add rules for specific subcategories or sources, and set response and resolution targets."
      />
      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 1.5 }}>
        <Tab value="owners" label="Category owners" />
        <Tab value="rules" label="Routing rules" />
        <Tab value="sla" label="SLA policies" />
      </Tabs>

      {tab === 'owners' ? (
        routesQuery.isLoading ? (
          <LoadingState message="Loading help desk routing…" />
        ) : routesQuery.isError ? (
          <Alert severity="error">{getErrorMessage(routesQuery.error)}</Alert>
        ) : (
          <Stack spacing={1.5}>
            {(routesQuery.data ?? []).map((route) => (
              <CategoryRouteCard
                key={`${route.category}-${route.assignee_user_id}-${route.backup_user_id}-${route.escalation_user_id}-${route.is_active}-${route.effective_from}`}
                route={route}
                users={users}
              />
            ))}
          </Stack>
        )
      ) : null}
      {tab === 'rules' ? <RoutingRulesTab users={users} /> : null}
      {tab === 'sla' ? <SlaTab /> : null}
    </PageContainer>
  );
}
