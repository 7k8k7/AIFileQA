import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchSessions,
  createSession,
  deleteSession,
  fetchMessages,
} from '../services';
import type { ScopeType } from '../types';

const SESSIONS_KEY = ['sessions'] as const;
const MESSAGES_KEY = (sessionId: string) => ['messages', sessionId] as const;

export function useSessions() {
  return useQuery({
    queryKey: SESSIONS_KEY,
    queryFn: fetchSessions,
  });
}

export function useCreateSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { scope_type: ScopeType; document_id?: string }) =>
      createSession(params),
    onSuccess: () => qc.invalidateQueries({ queryKey: SESSIONS_KEY }),
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: SESSIONS_KEY }),
  });
}

export function useMessages(sessionId: string | undefined) {
  return useQuery({
    queryKey: MESSAGES_KEY(sessionId ?? ''),
    queryFn: () => fetchMessages(sessionId!),
    enabled: !!sessionId,
  });
}

export function useInvalidateMessages() {
  const qc = useQueryClient();
  return (sessionId: string) =>
    qc.invalidateQueries({ queryKey: MESSAGES_KEY(sessionId) });
}
