import type { ChatSession, ChatMessage, ScopeType } from '../types';
import { mockSessions, mockMessages, mockStreamTokens } from './mock-data';

// ── Mock state ──

let sessions = [...mockSessions];
let messages: Record<string, ChatMessage[]> = JSON.parse(
  JSON.stringify(mockMessages),
);
const delay = (ms = 300) => new Promise((r) => setTimeout(r, ms));

// ── Sessions ──

export async function fetchSessions(): Promise<ChatSession[]> {
  await delay();
  return [...sessions].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );
}

export async function createSession(params: {
  scope_type: ScopeType;
  document_id?: string;
}): Promise<ChatSession> {
  await delay();
  const session: ChatSession = {
    id: `s-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: '新对话',
    scope_type: params.scope_type,
    document_id: params.document_id,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  sessions = [session, ...sessions];
  messages[session.id] = [];
  return session;
}

export async function deleteSession(id: string): Promise<void> {
  await delay();
  sessions = sessions.filter((s) => s.id !== id);
  delete messages[id];
}

// ── Messages ──

export async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  await delay();
  return messages[sessionId] ?? [];
}

/**
 * Simulate SSE streaming. Calls `onToken` for each chunk, `onDone` when complete.
 * Returns an abort function.
 */
export function sendMessage(
  sessionId: string,
  content: string,
  callbacks: {
    onToken: (token: string) => void;
    onDone: (messageId: string) => void;
    onError: (error: Error) => void;
  },
): () => void {
  let aborted = false;

  // Add user message immediately
  const userMsg: ChatMessage = {
    id: `m-${Date.now()}-u`,
    session_id: sessionId,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  };
  if (!messages[sessionId]) messages[sessionId] = [];
  messages[sessionId].push(userMsg);

  // Update session title from first message
  const session = sessions.find((s) => s.id === sessionId);
  if (session && session.title === '新对话') {
    session.title = content.slice(0, 50);
  }

  // Stream tokens
  const tokens = [...mockStreamTokens];
  const assistantId = `m-${Date.now()}-a`;
  let fullContent = '';
  let tokenIndex = 0;

  const interval = setInterval(() => {
    if (aborted) {
      clearInterval(interval);
      return;
    }
    if (tokenIndex >= tokens.length) {
      clearInterval(interval);
      // Save assistant message
      const assistantMsg: ChatMessage = {
        id: assistantId,
        session_id: sessionId,
        role: 'assistant',
        content: fullContent,
        created_at: new Date().toISOString(),
      };
      messages[sessionId].push(assistantMsg);
      if (session) session.updated_at = new Date().toISOString();
      callbacks.onDone(assistantId);
      return;
    }
    const token = tokens[tokenIndex++];
    fullContent += token;
    callbacks.onToken(token);
  }, 50);

  return () => {
    aborted = true;
    clearInterval(interval);
  };
}
