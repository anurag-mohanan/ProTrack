import {
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect, useMemo, useState } from 'react';
import type { Team } from '../../types/Team';

type RoomTeamsDialogProps = {
  open: boolean;
  teams: Team[];
  selectedIds: string[] | null;
  roomName: string;
  onClose: () => void;
  onSave: (next: { teamIds: string[] | null; roomName: string }) => void;
};

export function RoomTeamsDialog({
  open,
  teams,
  selectedIds,
  roomName,
  onClose,
  onSave,
}: RoomTeamsDialogProps) {
  const allIds = useMemo(() => teams.map((team) => team.id), [teams]);
  const [draftIds, setDraftIds] = useState<string[]>(selectedIds ?? allIds);
  const [draftName, setDraftName] = useState(roomName);

  useEffect(() => {
    if (!open) return;
    setDraftIds(selectedIds ?? allIds);
    setDraftName(roomName);
  }, [open, selectedIds, allIds, roomName]);

  const allSelected = allIds.length > 0 && allIds.every((id) => draftIds.includes(id));

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Room display teams</DialogTitle>
      <DialogContent>
        <Typography sx={{ color: 'text.secondary', mb: 2, fontSize: '0.9rem' }}>
          Choose which teams appear on this wall TV. Empty teams still show as placeholders. Settings
          stay on this browser (bookmark with <code>?teams=</code> for other rooms).
        </Typography>
        <TextField
          label="Room name (optional)"
          placeholder="e.g. Engineering Floor North"
          value={draftName}
          onChange={(event) => setDraftName(event.target.value)}
          fullWidth
          size="small"
          sx={{ mb: 2 }}
        />
        <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
          <Button size="small" onClick={() => setDraftIds(allIds)} disabled={allSelected}>
            Select all
          </Button>
          <Button size="small" onClick={() => setDraftIds([])}>
            Clear
          </Button>
        </Stack>
        <Box
          sx={{
            maxHeight: 320,
            overflowY: 'auto',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            px: 1.5,
            py: 0.5,
          }}
        >
          {teams.length ? (
            teams.map((team) => {
              const checked = draftIds.includes(team.id);
              return (
                <FormControlLabel
                  key={team.id}
                  control={
                    <Checkbox
                      checked={checked}
                      onChange={(event) => {
                        setDraftIds((prev) =>
                          event.target.checked
                            ? [...prev, team.id]
                            : prev.filter((id) => id !== team.id),
                        );
                      }}
                    />
                  }
                  label={team.name}
                />
              );
            })
          ) : (
            <Typography sx={{ py: 2, color: 'text.secondary' }}>No active teams found.</Typography>
          )}
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={draftIds.length === 0}
          onClick={() => {
            const showingAll =
              draftIds.length === allIds.length && allIds.every((id) => draftIds.includes(id));
            onSave({
              teamIds: showingAll ? null : draftIds,
              roomName: draftName.trim(),
            });
          }}
        >
          Save for this display
        </Button>
      </DialogActions>
    </Dialog>
  );
}
