import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Chip,
  Link,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { apiClient, getErrorMessage } from '../../api/client';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ContentCard } from '../../components/ui/cards';
import { ProsohmButton } from '../../components/ui/ProsohmButton';
import { useToast } from '../../context/ToastContext';

type ReadinessSummary = {
  signoffs_count: number;
  signoff_keys: string[];
  partners_count: number;
  partners_by_status: Record<string, number>;
  trust_open: number;
  trust_done: number;
  trust_must_fix_open: number;
  vision_d_ceo_signed: boolean;
  vision_d_cto_signed: boolean;
  require_sso_for_admins: boolean;
  audit_retention_days: number;
  oidc_enabled: boolean;
  oidc_testing: boolean;
  oidc_available: boolean;
  documents: Array<{ title: string; path: string }>;
};

type Signoff = {
  id: string;
  key: string;
  signer_name: string;
  signer_role: string;
  signed_at: string;
};

type Partner = {
  id: string;
  icp: string;
  company_name: string;
  status: string;
  contact_name: string | null;
  contact_email: string | null;
};

type TrustCheck = {
  id: string;
  control_id: string;
  title: string;
  severity: string;
  must_fix: boolean;
  status: string;
  owner: string | null;
  evidence_notes: string | null;
  doc_path: string | null;
};

const SIGNOFF_PRESETS = [
  { key: 'vision_d_ceo', role: 'CEO', label: 'Vision D — CEO' },
  { key: 'vision_d_cto', role: 'CTO', label: 'Vision D — CTO' },
  { key: 'soc2_gap_reviewed', role: 'CTO', label: 'SOC2 gap reviewed' },
  { key: 'entra_smoke_passed', role: 'Ops', label: 'Entra browser smoke passed' },
];

export default function CommercialReadinessPage() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [signerName, setSignerName] = useState('');
  const [signoffKey, setSignoffKey] = useState('vision_d_ceo');
  const [partnerCompany, setPartnerCompany] = useState('');
  const [partnerIcp, setPartnerIcp] = useState('mold');

  const summaryQuery = useQuery({
    queryKey: ['commercial', 'readiness', 'summary'],
    queryFn: async () =>
      (await apiClient.get<ReadinessSummary>('/commercial/readiness/summary')).data,
  });

  const signoffsQuery = useQuery({
    queryKey: ['commercial', 'readiness', 'signoffs'],
    queryFn: async () =>
      (await apiClient.get<Signoff[]>('/commercial/readiness/signoffs')).data,
  });

  const partnersQuery = useQuery({
    queryKey: ['commercial', 'readiness', 'partners'],
    queryFn: async () =>
      (await apiClient.get<Partner[]>('/commercial/readiness/partners')).data,
  });

  const trustQuery = useQuery({
    queryKey: ['commercial', 'readiness', 'trust'],
    queryFn: async () =>
      (await apiClient.get<TrustCheck[]>('/commercial/readiness/trust-checks')).data,
  });

  const accessQuery = useQuery({
    queryKey: ['commercial', 'readiness', 'access-review'],
    queryFn: async () =>
      (
        await apiClient.get<{ count: number; items: Array<Record<string, unknown>> }>(
          '/commercial/readiness/access-review',
        )
      ).data,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['commercial', 'readiness'] });
  };

  const signMutation = useMutation({
    mutationFn: async () => {
      const preset = SIGNOFF_PRESETS.find((p) => p.key === signoffKey);
      return apiClient.post('/commercial/readiness/signoffs', {
        key: signoffKey,
        signer_name: signerName,
        signer_role: preset?.role ?? 'Admin',
      });
    },
    onSuccess: () => {
      showSuccess('Sign-off recorded');
      setSignerName('');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Sign-off failed'),
  });

  const partnerMutation = useMutation({
    mutationFn: async () =>
      apiClient.post('/commercial/readiness/partners', {
        icp: partnerIcp,
        company_name: partnerCompany,
        status: 'draft',
        loi_doc_ref:
          partnerIcp === 'mold'
            ? 'docs/R10_LOI_DESIGN_PARTNER_MOLD.md'
            : partnerIcp === 'fixture'
              ? 'docs/R10_LOI_DESIGN_PARTNER_FIXTURE.md'
              : 'docs/R10_LOI_DESIGN_PARTNER_AUTO.md',
      }),
    onSuccess: () => {
      showSuccess('Design partner added');
      setPartnerCompany('');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not add partner'),
  });

  const partnerStatusMutation = useMutation({
    mutationFn: async (payload: { id: string; status: string }) =>
      apiClient.patch(`/commercial/readiness/partners/${payload.id}`, {
        status: payload.status,
      }),
    onSuccess: () => {
      showSuccess('Partner updated');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Update failed'),
  });

  const trustMutation = useMutation({
    mutationFn: async (payload: { control_id: string; status: string }) =>
      apiClient.patch(`/commercial/readiness/trust-checks/${payload.control_id}`, {
        status: payload.status,
      }),
    onSuccess: () => {
      showSuccess('Trust control updated');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Update failed'),
  });

  const ssoMutation = useMutation({
    mutationFn: async (enabled: boolean) =>
      apiClient.put('/commercial/readiness/require-sso-for-admins', { enabled }),
    onSuccess: () => {
      showSuccess('Admin SSO gate updated');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Could not update SSO gate'),
  });

  const accessAttestMutation = useMutation({
    mutationFn: async () => {
      const now = new Date();
      const q = Math.floor(now.getMonth() / 3) + 1;
      return apiClient.post('/commercial/readiness/signoffs', {
        key: `access_review_${now.getFullYear()}_Q${q}`,
        signer_name: signerName || 'Admin',
        signer_role: 'Admin',
        notes: `Attested ${accessQuery.data?.count ?? 0} privileged users`,
      });
    },
    onSuccess: () => {
      showSuccess('Access review attestation recorded');
      invalidate();
    },
    onError: (error) => showError(getErrorMessage(error) || 'Attestation failed'),
  });

  const summary = summaryQuery.data;
  const selectedPreset = useMemo(
    () => SIGNOFF_PRESETS.find((p) => p.key === signoffKey),
    [signoffKey],
  );

  if (summaryQuery.isLoading) {
    return <LoadingState message="Loading commercial readiness…" />;
  }

  return (
    <Stack spacing={2}>
      <PageHeader
        title="Commercial readiness"
        subtitle="GTM sign-offs, design partners, Entra/SSO posture, and SOC2 must-fix checklist."
      />

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Summary
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
          <Chip
            label={`Vision D CEO: ${summary?.vision_d_ceo_signed ? 'signed' : 'open'}`}
            color={summary?.vision_d_ceo_signed ? 'success' : 'default'}
          />
          <Chip
            label={`Vision D CTO: ${summary?.vision_d_cto_signed ? 'signed' : 'open'}`}
            color={summary?.vision_d_cto_signed ? 'success' : 'default'}
          />
          <Chip label={`Partners: ${summary?.partners_count ?? 0}`} />
          <Chip
            label={`Must-fix open: ${summary?.trust_must_fix_open ?? 0}`}
            color={(summary?.trust_must_fix_open ?? 0) > 0 ? 'warning' : 'success'}
          />
          <Chip
            label={`OIDC: ${summary?.oidc_available ? 'available' : 'off'}`}
            color={summary?.oidc_available ? 'success' : 'default'}
          />
          <Chip label={`Audit retention: ${summary?.audit_retention_days ?? '—'}d`} />
        </Stack>
      </ContentCard>

      <ContentCard>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          sx={{ justifyContent: 'space-between', alignItems: { sm: 'center' }, mb: 1 }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Admin SSO gate (S2)
          </Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography variant="body2">Require SSO for admins</Typography>
            <Switch
              checked={Boolean(summary?.require_sso_for_admins)}
              disabled={ssoMutation.isPending}
              onChange={(_, checked) => ssoMutation.mutate(checked)}
            />
          </Stack>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          When enabled, Admin password login is blocked. Use Entra SSO. Break-glass env:
          PROTRACK_SSO_BREAK_GLASS.
        </Typography>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Sign-offs
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 1.5 }}>
          <TextField
            select
            size="small"
            label="Key"
            value={signoffKey}
            onChange={(e) => setSignoffKey(e.target.value)}
            sx={{ minWidth: 220 }}
          >
            {SIGNOFF_PRESETS.map((p) => (
              <MenuItem key={p.key} value={p.key}>
                {p.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Signer name"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            fullWidth
          />
          <ProsohmButton
            size="small"
            disabled={!signerName || signMutation.isPending}
            onClick={() => signMutation.mutate()}
          >
            Record ({selectedPreset?.role})
          </ProsohmButton>
        </Stack>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Key</TableCell>
              <TableCell>Signer</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Signed</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(signoffsQuery.data ?? []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.key}</TableCell>
                <TableCell>{row.signer_name}</TableCell>
                <TableCell>{row.signer_role}</TableCell>
                <TableCell>{new Date(row.signed_at).toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Design partners
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 1.5 }}>
          <TextField
            select
            size="small"
            label="ICP"
            value={partnerIcp}
            onChange={(e) => setPartnerIcp(e.target.value)}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="mold">Mold</MenuItem>
            <MenuItem value="fixture">Fixture</MenuItem>
            <MenuItem value="auto">Auto</MenuItem>
          </TextField>
          <TextField
            size="small"
            label="Company"
            value={partnerCompany}
            onChange={(e) => setPartnerCompany(e.target.value)}
            fullWidth
          />
          <ProsohmButton
            size="small"
            disabled={!partnerCompany || partnerMutation.isPending}
            onClick={() => partnerMutation.mutate()}
          >
            Add
          </ProsohmButton>
        </Stack>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Company</TableCell>
              <TableCell>ICP</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Advance</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(partnersQuery.data ?? []).map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.company_name}</TableCell>
                <TableCell>{row.icp}</TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell align="right">
                  {row.status === 'draft' ? (
                    <ProsohmButton
                      size="small"
                      buttonVariant="outlined"
                      onClick={() =>
                        partnerStatusMutation.mutate({ id: row.id, status: 'loi_sent' })
                      }
                    >
                      Mark LOI sent
                    </ProsohmButton>
                  ) : null}
                  {row.status === 'loi_sent' ? (
                    <ProsohmButton
                      size="small"
                      buttonVariant="outlined"
                      onClick={() =>
                        partnerStatusMutation.mutate({ id: row.id, status: 'signed' })
                      }
                    >
                      Mark signed
                    </ProsohmButton>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Trust checklist
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Title</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(trustQuery.data ?? []).map((row) => (
              <TableRow key={row.control_id}>
                <TableCell>
                  {row.control_id}
                  {row.must_fix ? ' *' : ''}
                </TableCell>
                <TableCell>
                  <Typography variant="body2">{row.title}</Typography>
                  {row.doc_path ? (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {row.doc_path}
                    </Typography>
                  ) : null}
                </TableCell>
                <TableCell>{row.status}</TableCell>
                <TableCell align="right">
                  {row.status !== 'done' ? (
                    <ProsohmButton
                      size="small"
                      buttonVariant="outlined"
                      onClick={() =>
                        trustMutation.mutate({ control_id: row.control_id, status: 'done' })
                      }
                    >
                      Mark done
                    </ProsohmButton>
                  ) : (
                    <ProsohmButton
                      size="small"
                      buttonVariant="outlined"
                      onClick={() =>
                        trustMutation.mutate({ control_id: row.control_id, status: 'open' })
                      }
                    >
                      Reopen
                    </ProsohmButton>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Typography variant="caption" color="text.secondary">
          * Must-fix before first external production tenant
        </Typography>
      </ContentCard>

      <ContentCard>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          sx={{ justifyContent: 'space-between', mb: 1.5 }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Access review ({accessQuery.data?.count ?? 0} privileged users)
          </Typography>
          <ProsohmButton
            size="small"
            buttonVariant="outlined"
            onClick={() => accessAttestMutation.mutate()}
            disabled={accessAttestMutation.isPending}
          >
            Attest this quarter
          </ProsohmButton>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          CSV export: GET /api/v1/commercial/readiness/access-review?format=csv
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Email</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Active</TableCell>
              <TableCell>SSO</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(accessQuery.data?.items ?? []).slice(0, 20).map((row) => (
              <TableRow key={String(row.user_id)}>
                <TableCell>{String(row.email)}</TableCell>
                <TableCell>{String(row.role)}</TableCell>
                <TableCell>{row.is_active ? 'yes' : 'no'}</TableCell>
                <TableCell>{row.sso_subject ? 'linked' : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ContentCard>

      <ContentCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
          Trust document pack
        </Typography>
        <Stack spacing={0.5}>
          {(summary?.documents ?? []).map((doc) => (
            <Typography key={doc.path} variant="body2">
              <Link component="span" underline="hover">
                {doc.title}
              </Link>
              <Typography component="span" variant="caption" color="text.secondary">
                {' '}
                — {doc.path}
              </Typography>
            </Typography>
          ))}
        </Stack>
      </ContentCard>
    </Stack>
  );
}
