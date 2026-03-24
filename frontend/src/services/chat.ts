import type { ChatSession, ChatMessage, ScopeType, SourceChunk } from '../types';
import api from './api';
import { sseStream } from './api';

// ── Sessions ──

export async function fetchSessions(): Promise<ChatSession[]> {
  const { data } = await api.get<ChatSession[]>('/chat/sessions');
  return data;
}

export async function createSession(params: {
  scope_type: ScopeType;
  provider_id?: string;
  document_id?: string;
  document_ids?: string[];
}): Promise<ChatSession> {
  const { data } = await api.post<ChatSession>('/chat/sessions', params);
  return data;
}

export async function deleteSession(id: string): Promise<void> {
  await api.delete(`/chat/sessions/${id}`);
}

// ── Messages ──

export async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`);
  return data;
}

/**
 * Send a user message and stream the LLM response via SSE.
 * Returns an abort function.
 */
export function sendMessage(
  sessionId: string,
  content: string,
  callbacks: {
    onToken: (token: string) => void;
    onDone: (messageId: string) => void;
    onError: (error: Error) => void;
    onAccepted?: (data: { userMessageId?: string }) => void;
    onSources?: (data: { retrieval_method: string; chunks: SourceChunk[] }) => void;
  },
): () => void {
  return sseStream(
    `/chat/sessions/${sessionId}/messages`,
    { content },
    callbacks,
  );
}

export function regenerateMessage(
  sessionId: string,
  messageId: string,
  callbacks: {
    onToken: (token: string) => void;
    onDone: (messageId: string) => void;
    onError: (error: Error) => void;
    onAccepted?: (data: { userMessageId?: string }) => void;
    onSources?: (data: { retrieval_method: string; chunks: SourceChunk[] }) => void;
  },
): () => void {
  return sseStream(
    `/chat/sessions/${sessionId}/messages/${messageId}/regenerate`,
    {},
    callbacks,
  );
}
