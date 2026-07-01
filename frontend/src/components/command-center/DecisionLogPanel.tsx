import {
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import { useMemo, useState } from 'react';
import type { DecisionCategory, ProjectDecision } from '../../types/CommandCenter';
import { formatDateTime } from '../../utils/format';
import { EmptyState } from '../common/EmptyState';

const CATEGORIES: { value: DecisionCategory; label: string }[] = [
  { value: 'design', label: 'Design' },
  { value: 'customer', label: 'Customer' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'tooling', label: 'Tooling' },
  { value: 'schedule', label: 'Schedule' },
  { value: 'quality', label: 'Quality' },
  { value: 'general', label: 'General' },
];

interface DecisionLogPanelProps {
  decisions: ProjectDecision[];
  onCreate: (payload: {
    category: DecisionCategory;
    comment: string;
    milestone_id?: string | null;
  }) => void;
  onUpdate: (
    id: string,
    payload: { category?: DecisionCategory; comment?: string },
  ) => void;
  onDelete: (id: string) => void;
  loading?: boolean;
}

export function DecisionLogPanel({
  decisions,
  onCreate,
  onUpdate,
  onDelete,
  loading = false,
}: DecisionLogPanelProps) {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [draftCategory, setDraftCategory] = useState<DecisionCategory>('general');
  const [draftComment, setDraftComment] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editComment, setEditComment] = useState('');

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return decisions.filter((row) => {
      if (categoryFilter !== 'all' && row.category !== categoryFilter) return false;
      if (!term) return true;
      return [row.comment, row.user_name ?? '', row.milestone_name ?? '', row.category]
        .join(' ')
        .toLowerCase()
        .includes(term);
    });
  }, [categoryFilter, decisions, search]);

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        <TextField
          size="small"
          label="Search decisions"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ minWidth: 200, flex: 1 }}
        />
        <TextField
          select
          size="small"
          label="Category"
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(event.target.value)}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="all">All categories</MenuItem>
          {CATEGORIES.map((item) => (
            <MenuItem key={item.value} value={item.value}>
              {item.label}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
        <TextField
          select
          size="small"
          label="Category"
          value={draftCategory}
          onChange={(event) => setDraftCategory(event.target.value as DecisionCategory)}
          sx={{ minWidth: 140 }}
        >
          {CATEGORIES.map((item) => (
            <MenuItem key={item.value} value={item.value}>
              {item.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Decision comment"
          value={draftComment}
          onChange={(event) => setDraftComment(event.target.value)}
          sx={{ flex: 1, minWidth: 220 }}
        />
        <Button
          variant="contained"
          disabled={!draftComment.trim() || loading}
          onClick={() => {
            onCreate({ category: draftCategory, comment: draftComment.trim() });
            setDraftComment('');
          }}
        >
          Add Decision
        </Button>
      </Box>

      {!filtered.length ? (
        <EmptyState title="No decisions logged" />
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>User</TableCell>
              <TableCell>Category</TableCell>
              <TableCell>Milestone</TableCell>
              <TableCell>Comment</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filtered.map((row) => (
              <TableRow key={row.id} hover>
                <TableCell>{formatDateTime(row.created_at)}</TableCell>
                <TableCell>{row.user_name ?? '—'}</TableCell>
                <TableCell>
                  <Chip size="small" label={row.category} variant="outlined" />
                </TableCell>
                <TableCell>{row.milestone_name ?? '—'}</TableCell>
                <TableCell sx={{ maxWidth: 320 }}>
                  {editingId === row.id ? (
                    <TextField
                      size="small"
                      fullWidth
                      value={editComment}
                      onChange={(event) => setEditComment(event.target.value)}
                    />
                  ) : (
                    row.comment
                  )}
                </TableCell>
                <TableCell align="right">
                  {editingId === row.id ? (
                    <Button
                      size="small"
                      onClick={() => {
                        onUpdate(row.id, { comment: editComment });
                        setEditingId(null);
                      }}
                    >
                      Save
                    </Button>
                  ) : (
                    <>
                      <IconButton
                        size="small"
                        onClick={() => {
                          setEditingId(row.id);
                          setEditComment(row.comment);
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => onDelete(row.id)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
}
