import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import type { Workstream } from '../../../types';
import type { WorkstreamSectionPrefs } from '../../../utils/projectWorkstreamGroups';

interface WorkstreamSectionsManagerProps {
  open: boolean;
  onClose: () => void;
  catalog: Workstream[];
  prefs: WorkstreamSectionPrefs;
  onChange: (next: WorkstreamSectionPrefs) => void;
}

export function WorkstreamSectionsManager({
  open,
  onClose,
  catalog,
  prefs,
  onChange,
}: WorkstreamSectionsManagerProps) {
  const active = catalog
    .filter((ws) => ws.is_active !== false)
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0) || a.name.localeCompare(b.name));

  const hidden = new Set(prefs.hidden);
  const byId = new Map(active.map((ws) => [ws.id, ws]));

  const orderedIds = (() => {
    const ids = active.map((ws) => ws.id).filter((id) => !hidden.has(id));
    if (!prefs.order.length) return ids;
    const set = new Set(ids);
    const custom = prefs.order.filter((id) => set.has(id));
    const rest = ids.filter((id) => !custom.includes(id));
    return [...custom, ...rest];
  })();

  const move = (id: string, delta: number) => {
    const next = [...orderedIds];
    const index = next.indexOf(id);
    if (index < 0) return;
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    const [row] = next.splice(index, 1);
    next.splice(target, 0, row);
    onChange({ ...prefs, order: next });
  };

  const reset = () => {
    onChange({
      order: [],
      hidden: [],
      pinned: prefs.pinned,
      collapsed: prefs.collapsed,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <TuneRoundedIcon fontSize="small" />
        Workstream sections
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Reorder engineering disciplines. Favourites stay pinned at the top of the Projects Command
          Center. New workstreams from admin appear automatically.
        </Typography>
        <List dense disablePadding>
          {orderedIds.map((id, index) => {
            const ws = byId.get(id);
            if (!ws) return null;
            return (
              <ListItem
                key={id}
                secondaryAction={
                  <Stack direction="row" spacing={0.25}>
                    <IconButton
                      size="small"
                      aria-label="Move up"
                      disabled={index === 0}
                      onClick={() => move(id, -1)}
                    >
                      <ArrowUpwardIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      aria-label="Move down"
                      disabled={index === orderedIds.length - 1}
                      onClick={() => move(id, 1)}
                    >
                      <ArrowDownwardIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                }
                sx={{ borderBottom: '1px solid', borderColor: 'divider', pr: 10 }}
              >
                <ListItemText
                  primary={ws.name}
                  secondary={ws.code ? `Code ${ws.code}` : undefined}
                />
              </ListItem>
            );
          })}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={reset} color="inherit">
          Reset order
        </Button>
        <Button onClick={onClose} variant="contained">
          Done
        </Button>
      </DialogActions>
    </Dialog>
  );
}
