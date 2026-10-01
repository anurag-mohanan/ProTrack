import type { SvgIconComponent } from '@mui/icons-material';
import AssignmentLateRoundedIcon from '@mui/icons-material/AssignmentLateRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import ComputerRoundedIcon from '@mui/icons-material/ComputerRounded';
import EventRoundedIcon from '@mui/icons-material/EventRounded';
import FiberNewRoundedIcon from '@mui/icons-material/FiberNewRounded';
import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
import InboxRoundedIcon from '@mui/icons-material/InboxRounded';
import KeyRoundedIcon from '@mui/icons-material/KeyRounded';
import PersonAddAltRoundedIcon from '@mui/icons-material/PersonAddAltRounded';
import PersonOffRoundedIcon from '@mui/icons-material/PersonOffRounded';
import PlayCircleRoundedIcon from '@mui/icons-material/PlayCircleRounded';
import PriorityHighRoundedIcon from '@mui/icons-material/PriorityHighRounded';
import type { TicketPriority, TicketStatus } from '../../types/tickets';

export type ChipColor = 'default' | 'primary' | 'info' | 'warning' | 'error' | 'success' | 'secondary';

export const STATUS_COLOR: Record<TicketStatus, ChipColor> = {
  new: 'secondary',
  open: 'info',
  in_progress: 'primary',
  pending_requester: 'warning',
  pending_internal: 'warning',
  pending_vendor: 'warning',
  on_hold: 'warning',
  resolved: 'success',
  closed: 'default',
  cancelled: 'default',
};

export const PRIORITY_COLOR: Record<TicketPriority, ChipColor> = {
  low: 'default',
  normal: 'info',
  medium: 'info',
  high: 'warning',
  urgent: 'error',
};

export const PENDING_STATUSES: readonly TicketStatus[] = [
  'pending_requester',
  'pending_internal',
  'pending_vendor',
];

export const ACTION_LABELS: Partial<Record<TicketStatus, string>> = {
  open: 'Reopen',
  in_progress: 'Start work',
  pending_requester: 'Waiting on requester',
  pending_internal: 'Waiting on internal team',
  pending_vendor: 'Waiting on vendor',
  resolved: 'Resolve',
  closed: 'Close',
  cancelled: 'Cancel ticket',
};

/** Statuses that need a dialog (reason or resolution) before submitting. */
export const NEEDS_DIALOG: ReadonlySet<TicketStatus> = new Set<TicketStatus>([
  'pending_requester',
  'pending_internal',
  'pending_vendor',
  'resolved',
  'closed',
  'cancelled',
  'open',
]);

export interface QueueCard {
  key: string;
  label: string;
  view?: string;
  status?: string;
  icon: SvgIconComponent;
  accent?: 'primary' | 'info' | 'warning' | 'error' | 'success';
}

/** Work-queue cards: each opens the matching filtered list. */
export const IT_QUEUE_CARDS: readonly QueueCard[] = [
  { key: 'new', label: 'New', status: 'new', icon: FiberNewRoundedIcon, accent: 'primary' },
  { key: 'open', label: 'Open', status: 'open', icon: InboxRoundedIcon, accent: 'info' },
  { key: 'in_progress', label: 'In progress', status: 'in_progress', icon: PlayCircleRoundedIcon, accent: 'primary' },
  { key: 'waiting', label: 'Waiting', status: 'waiting', icon: HourglassEmptyRoundedIcon, accent: 'warning' },
  { key: 'resolved', label: 'Resolved', status: 'resolved', icon: CheckCircleRoundedIcon, accent: 'success' },
  { key: 'overdue', label: 'Overdue', view: 'overdue', icon: AssignmentLateRoundedIcon, accent: 'error' },
  { key: 'unassigned', label: 'Unassigned', view: 'unassigned', icon: PersonOffRoundedIcon, accent: 'warning' },
  { key: 'high', label: 'High priority', view: 'high', icon: PriorityHighRoundedIcon, accent: 'error' },
  { key: 'due_today', label: 'Due today', view: 'due_today', icon: EventRoundedIcon, accent: 'warning' },
  { key: 'onboarding', label: 'Onboarding', view: 'onboarding', icon: PersonAddAltRoundedIcon, accent: 'primary' },
  { key: 'hardware', label: 'Hardware', view: 'hardware', icon: ComputerRoundedIcon, accent: 'info' },
  { key: 'software', label: 'Software / licence', view: 'software', icon: KeyRoundedIcon, accent: 'info' },
];

export interface QueueView {
  value: string;
  label: string;
}

export const IT_QUEUE_VIEWS: readonly QueueView[] = [
  { value: 'mine', label: 'My tickets' },
  { value: 'team', label: 'IT team queue' },
  { value: 'unassigned', label: 'Unassigned' },
  { value: 'onboarding', label: 'Onboarding' },
  { value: 'hardware', label: 'Hardware' },
  { value: 'software', label: 'Software / licence' },
  { value: 'asset', label: 'Asset issues' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'recently_resolved', label: 'Recently resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'all', label: 'All tickets' },
];

export const HELP_DESK_VIEWS: readonly QueueView[] = [
  { value: 'raised', label: 'Raised by me' },
  { value: 'mine', label: 'Assigned to me' },
  { value: 'team', label: 'Queues I work' },
  { value: 'unassigned', label: 'Unassigned' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'all', label: 'All' },
];

export const DUE_FILTERS: readonly QueueView[] = [
  { value: '', label: 'Any due date' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'today', label: 'Due today' },
  { value: 'week', label: 'Due within 7 days' },
];

export function ticketHref(ticketId: string): string {
  return `/help-desk/tickets/${ticketId}`;
}
