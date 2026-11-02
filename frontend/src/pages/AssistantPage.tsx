import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  assistantQueryKeys,
  createConversation,
  deleteConversation,
  fetchAssistantStatus,
  fetchAssistantSuggestions,
  fetchConversation,
  fetchConversations,
  renameConversation,
  sendAssistantMessage,
  sendMessageFeedback,
  type AssistantConversation,
  type AssistantStatus,
  type AssistantSuggestion,
} from '../api/assistant';
import { getErrorMessage } from '../api/client';
import { AssistantMessageView } from '../components/assistant/AssistantMessageView';
import { RecommendationsPanel } from '../components/assistant/RecommendationsPanel';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { PageContainer } from '../components/common/PageContainer';
import { PageHeader } from '../components/common/PageHeader';
import { useToast } from '../context/ToastContext';
import { formatDateTime } from '../utils/format';

type AssistantTab = 'ask' | 'recommendations';
type AskInput = { text: string; suggestionId?: string };

function StatusBanner({ status }: { status: AssistantStatus }) {
  if (status.mode === 'disabled') {
    return <Alert severity="warning" sx={{ mb: 2 }}>{status.message}</Alert>;
  }
  if (status.mode === 'offline') {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>AI provider not configured.</strong> {status.message}
      </Alert>
    );
  }
  return (
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
      Answers use only the ProTrack records you are allowed to see, retrieved through ProTrack's own calculations. Check
      the sources and limitations under each answer; earlier answers are not re-checked automatically.
    </Typography>
  );
}

function SuggestionGrid({
  suggestions,
  onPick,
  disabled,
}: {
  suggestions: AssistantSuggestion[];
  onPick: (s: AssistantSuggestion) => void;
  disabled: boolean;
}) {
  const groups = useMemo(() => {
    const out = new Map<string, AssistantSuggestion[]>();
    for (const s of suggestions) out.set(s.category, [...(out.get(s.category) ?? []), s]);
    return [...out.entries()];
  }, [suggestions]);

  if (!groups.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No suggested questions are available for your access and the data currently in ProTrack.
      </Typography>
    );
  }
  return (
    <Stack sx={{ gap: 2 }}>
      {groups.map(([category, items]) => (
        <Box key={category}>
          <Typography variant="overline" color="text.secondary">
            {category}
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {items.map((s) => (
              <Chip key={s.id} label={s.text} variant="outlined" onClick={() => onPick(s)} disabled={disabled} />
            ))}
          </Box>
        </Box>
      ))}
    </Stack>
  );
}

function ConversationList({
  conversations,
  selectedId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: {
  conversations: AssistantConversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (c: AssistantConversation) => void;
  onDelete: (c: AssistantConversation) => void;
}) {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden', alignSelf: 'start' }}>
      <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
        <Button fullWidth variant="contained" startIcon={<AddRoundedIcon />} onClick={onNew}>
          New conversation
        </Button>
      </Box>
      {conversations.length ? (
        <List dense disablePadding sx={{ maxHeight: 'calc(100vh - 320px)', overflow: 'auto' }}>
          {conversations.map((c) => (
            <ListItemButton
              key={c.id}
              selected={c.id === selectedId}
              onClick={() => onSelect(c.id)}
              sx={{ pr: 10, position: 'relative' }}
            >
              <ListItemText
                primary={c.title}
                secondary={formatDateTime(c.last_message_at ?? c.created_at)}
                slotProps={{ primary: { noWrap: true, variant: 'body2' }, secondary: { variant: 'caption' } }}
              />
              <Box sx={{ position: 'absolute', right: 4, display: 'flex' }}>
                <Tooltip title="Rename">
                  <IconButton
                    size="small"
                    aria-label={`Rename ${c.title}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRename(c);
                    }}
                  >
                    <EditOutlinedIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete">
                  <IconButton
                    size="small"
                    aria-label={`Delete ${c.title}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c);
                    }}
                  >
                    <DeleteOutlineRoundedIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            </ListItemButton>
          ))}
        </List>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
          No conversations yet.
        </Typography>
      )}
    </Paper>
  );
}

function AskPanel({ status }: { status: AssistantStatus }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get('c');
  const [draft, setDraft] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<AssistantConversation | null>(null);
  const [renameTitle, setRenameTitle] = useState('');
  const [deleting, setDeleting] = useState<AssistantConversation | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversationsQuery = useQuery({ queryKey: assistantQueryKeys.conversations, queryFn: fetchConversations });
  const suggestionsQuery = useQuery({ queryKey: assistantQueryKeys.suggestions, queryFn: fetchAssistantSuggestions });
  const conversationQuery = useQuery({
    queryKey: assistantQueryKeys.conversation(selectedId ?? ''),
    queryFn: () => fetchConversation(selectedId!),
    enabled: Boolean(selectedId),
  });

  const select = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set('c', id);
    else next.delete('c');
    setParams(next, { replace: true });
  };

  const askMutation = useMutation({
    mutationFn: async ({ text, suggestionId }: AskInput) => {
      let id = selectedId;
      if (!id) {
        id = (await createConversation()).id;
        select(id);
      }
      await sendAssistantMessage(id, text, suggestionId);
      return id;
    },
    onSuccess: async (id) => {
      setDraft('');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: assistantQueryKeys.conversation(id) }),
        queryClient.invalidateQueries({ queryKey: assistantQueryKeys.conversations }),
        queryClient.invalidateQueries({ queryKey: ['assistant', 'recommendations'] }),
      ]);
    },
    onError: (error) => setSendError(getErrorMessage(error)),
  });

  const feedbackMutation = useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: 'up' | 'down' | null }) => sendMessageFeedback(id, rating),
    onSuccess: () => {
      if (selectedId) void queryClient.invalidateQueries({ queryKey: assistantQueryKeys.conversation(selectedId) });
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameConversation(id, title),
    onSuccess: async (row) => {
      setRenaming(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: assistantQueryKeys.conversations }),
        queryClient.invalidateQueries({ queryKey: assistantQueryKeys.conversation(row.id) }),
      ]);
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: async (_, id) => {
      setDeleting(null);
      if (id === selectedId) select(null);
      await queryClient.invalidateQueries({ queryKey: assistantQueryKeys.conversations });
    },
    onError: (error) => toast.showError(getErrorMessage(error)),
  });

  const messages = selectedId ? (conversationQuery.data?.messages ?? []) : [];
  const pending = askMutation.isPending ? askMutation.variables : undefined;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, pending]);

  const disabled = status.mode === 'disabled' || askMutation.isPending;
  const maxChars = status.limits.max_input_chars;
  const trimmed = draft.trim();

  const ask = (input: AskInput) => {
    if (disabled || !input.text.trim()) return;
    setSendError(null);
    askMutation.mutate({ ...input, text: input.text.trim() });
  };

  const copy = (text: string) => {
    void navigator.clipboard
      .writeText(text)
      .then(() => toast.showSuccess('Answer copied.'))
      .catch(() => toast.showError('Copying is not available in this browser.'));
  };

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '280px minmax(0, 1fr)' }, gap: 2 }}>
      <ConversationList
        conversations={conversationsQuery.data ?? []}
        selectedId={selectedId}
        onSelect={select}
        onNew={() => select(null)}
        onRename={(c) => {
          setRenaming(c);
          setRenameTitle(c.title);
        }}
        onDelete={setDeleting}
      />

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <StatusBanner status={status} />

        <Box sx={{ flex: 1, minHeight: 320, maxHeight: 'calc(100vh - 360px)', overflow: 'auto', pr: 0.5 }}>
          {conversationQuery.error ? (
            <ErrorState error={conversationQuery.error} onRetry={() => void conversationQuery.refetch()} />
          ) : null}
          {selectedId && conversationQuery.isLoading ? <LoadingState message="Loading conversation…" /> : null}

          {!messages.length && !pending ? (
            <Box sx={{ py: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <SmartToyRoundedIcon color="primary" />
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  Ask about projects, resources, finance or delivery performance
                </Typography>
              </Box>
              {suggestionsQuery.isLoading ? <LoadingState message="Loading suggestions…" /> : null}
              {suggestionsQuery.error ? <ErrorState error={suggestionsQuery.error} /> : null}
              {suggestionsQuery.data ? (
                <SuggestionGrid
                  suggestions={suggestionsQuery.data}
                  disabled={disabled}
                  onPick={(s) => ask({ text: s.text, suggestionId: s.id })}
                />
              ) : null}
            </Box>
          ) : null}

          <Stack sx={{ gap: 1.5 }}>
            {messages.map((m) => (
              <AssistantMessageView
                key={m.id}
                message={m}
                disabled={disabled}
                onAsk={(text) => ask({ text })}
                onCopy={copy}
                onFeedback={(rating) => feedbackMutation.mutate({ id: m.id, rating })}
              />
            ))}
            {pending ? (
              <>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Paper
                    elevation={0}
                    sx={{ px: 2, py: 1.25, maxWidth: '80%', bgcolor: 'primary.main', color: 'primary.contrastText', borderRadius: 2, opacity: 0.8 }}
                  >
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                      {pending.text}
                    </Typography>
                  </Paper>
                </Box>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Checking ProTrack data…
                  </Typography>
                  <LinearProgress />
                </Paper>
              </>
            ) : null}
          </Stack>
          <div ref={bottomRef} />
        </Box>

        {sendError ? (
          <Alert severity="error" sx={{ mt: 1.5 }} onClose={() => setSendError(null)}>
            {sendError}
          </Alert>
        ) : null}

        <Box
          component="form"
          sx={{ display: 'flex', gap: 1, mt: 1.5, alignItems: 'flex-end' }}
          onSubmit={(e) => {
            e.preventDefault();
            ask({ text: draft });
          }}
        >
          <TextField
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                ask({ text: draft });
              }
            }}
            placeholder={
              status.mode === 'llm'
                ? 'Ask a question about ProTrack data…'
                : status.mode === 'offline'
                  ? 'Free-text questions need an AI provider. Use a suggested question above.'
                  : 'The assistant is switched off.'
            }
            multiline
            maxRows={6}
            fullWidth
            size="small"
            disabled={status.mode === 'disabled'}
            error={draft.length > maxChars}
            helperText={draft.length > maxChars * 0.8 ? `${draft.length} / ${maxChars} characters` : ' '}
            slotProps={{ htmlInput: { 'aria-label': 'Question' } }}
          />
          <Button
            type="submit"
            variant="contained"
            endIcon={<SendRoundedIcon />}
            disabled={disabled || !trimmed || draft.length > maxChars}
            sx={{ mb: 2.75 }}
          >
            Ask
          </Button>
        </Box>
      </Paper>

      <Dialog open={renaming !== null} onClose={() => setRenaming(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Rename conversation</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            margin="dense"
            label="Title"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            slotProps={{ htmlInput: { maxLength: 200 } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRenaming(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!renameTitle.trim() || renameMutation.isPending}
            onClick={() => renaming && renameMutation.mutate({ id: renaming.id, title: renameTitle.trim() })}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete conversation"
        recordName={deleting?.title}
        message="The conversation is removed from your history. Its messages, any recommendations it produced and the data-access audit are retained for review."
        confirmLabel="Delete"
        danger
        loading={deleteMutation.isPending}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />
    </Box>
  );
}

export default function AssistantPage() {
  const [params, setParams] = useSearchParams();
  const statusQuery = useQuery({ queryKey: assistantQueryKeys.status, queryFn: fetchAssistantStatus });
  const tab: AssistantTab = params.get('tab') === 'recommendations' ? 'recommendations' : 'ask';

  if (statusQuery.isLoading) return <LoadingState message="Loading assistant…" />;
  if (statusQuery.error) return <ErrorState error={statusQuery.error} onRetry={() => void statusQuery.refetch()} />;
  const status = statusQuery.data!;

  return (
    <PageContainer>
      <PageHeader subtitle="Ask about projects, milestones, risk, capacity, skills, billing and delivery performance. Answers are grounded in ProTrack records you can access and cite their sources. The assistant only recommends; it never changes records." />
      <Tabs
        value={tab}
        onChange={(_, value: AssistantTab) => {
          const next = new URLSearchParams(params);
          if (value === 'ask') next.delete('tab');
          else next.set('tab', value);
          setParams(next, { replace: true });
        }}
        sx={{ mb: 2, minHeight: 40, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab value="ask" label="Ask" sx={{ minHeight: 40 }} />
        <Tab value="recommendations" label="Recommendations" sx={{ minHeight: 40 }} />
      </Tabs>
      {tab === 'ask' ? <AskPanel status={status} /> : <RecommendationsPanel />}
    </PageContainer>
  );
}
