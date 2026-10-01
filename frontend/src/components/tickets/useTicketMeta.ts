import { useQuery } from '@tanstack/react-query';
import { ticketsApi } from '../../api/tickets';

export function useTicketCatalog() {
  return useQuery({
    queryKey: ['tickets', 'catalog'],
    queryFn: () => ticketsApi.catalog(),
    staleTime: 60 * 60 * 1000,
  });
}

export function useTicketCapabilities() {
  return useQuery({
    queryKey: ['tickets', 'me'],
    queryFn: () => ticketsApi.me(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTicketAssignees(category: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['tickets', 'assignees', category],
    queryFn: () => ticketsApi.assignees(category as string),
    enabled: Boolean(category) && enabled,
    staleTime: 5 * 60 * 1000,
  });
}
