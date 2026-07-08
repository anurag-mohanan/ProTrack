import { useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded';
import { useMutation } from '@tanstack/react-query';
import { sendAiChat } from '../../api/ai';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';

interface ChatEntry {
  role: 'user' | 'assistant';
  content: string;
}

const SUGGESTIONS = [
  'Show projects due this week',
  'Who is available for a 120-hour project?',
  'Which customer consumed the most hours this month?',
  'Which projects are at risk?',
];

export function AiChatAssistant() {
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState('');

  const chatMutation = useMutation({
    mutationFn: sendAiChat,
    onSuccess: (response) => {
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: response.answer },
      ]);
    },
  });

  const send = (text: string) => {
    const question = text.trim();
    if (!question || chatMutation.isPending) return;
    setMessages((current) => [...current, { role: 'user', content: question }]);
    setInput('');
    chatMutation.mutate(question);
  };

  return (
    <DashboardPanel
      title="AI Chat Assistant"
      subtitle="Ask about projects, workload, quotes, and risks"
    >
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap' }}>
          {SUGGESTIONS.map((suggestion) => (
            <Chip
              key={suggestion}
              label={suggestion}
              size="small"
              onClick={() => send(suggestion)}
              sx={{ cursor: 'pointer' }}
            />
          ))}
        </Stack>

        <Box
          sx={{
            maxHeight: 280,
            overflowY: 'auto',
            p: 1,
            borderRadius: 2,
            bgcolor: 'action.hover',
          }}
        >
          {messages.length === 0 ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', p: 1 }}>
              <SmartToyRoundedIcon color="primary" fontSize="small" />
              <Typography variant="body2" color="text.secondary">
                Ask a question about engineering operations.
              </Typography>
            </Stack>
          ) : (
            messages.map((msg, index) => (
              <Box
                key={index}
                sx={{
                  mb: 1,
                  p: 1,
                  borderRadius: 2,
                  bgcolor: msg.role === 'user' ? 'background.paper' : 'transparent',
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <Typography variant="body2">{msg.content}</Typography>
              </Box>
            ))
          )}
          {chatMutation.isPending ? <CircularProgress size={20} sx={{ m: 1 }} /> : null}
        </Box>

        <Stack direction="row" spacing={1}>
          <TextField
            size="small"
            fullWidth
            placeholder="Ask ProTrack..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                send(input);
              }
            }}
          />
          <IconButton color="primary" onClick={() => send(input)} disabled={chatMutation.isPending}>
            <SendRoundedIcon />
          </IconButton>
        </Stack>
      </Stack>
    </DashboardPanel>
  );
}
