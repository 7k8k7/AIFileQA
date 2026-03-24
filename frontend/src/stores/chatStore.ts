import { create } from 'zustand';
import type { ChatMessage, SourceChunk } from '../types';

export interface SourcesData {
  retrieval_method: string;
  chunks: SourceChunk[];
}

interface ChatUIState {
  /** Currently active session ID */
  activeSessionId: string | undefined;
  /** Streaming assistant content being built up */
  streamingContent: string;
  /** Whether a stream is currently active */
  isStreaming: boolean;
  /** Abort function for the current stream */
  abortStream: (() => void) | null;
  /** Retrieved sources for the current/last response */
  streamingSources: SourcesData | null;
  /** Optimistic user messages waiting for query refresh */
  optimisticMessages: ChatMessage[];
  /** Message currently being regenerated */
  regeneratingMessageId: string | null;

  setActiveSession: (id: string | undefined) => void;
  addOptimisticUserMessage: (sessionId: string, content: string) => string;
  commitOptimisticUserMessage: (tempId: string, realId: string) => void;
  clearConfirmedOptimisticMessages: (messages: ChatMessage[]) => void;
  clearOptimisticMessages: (sessionId?: string) => void;
  appendStreamToken: (token: string) => void;
  startStreaming: (abort: () => void, options?: { regeneratingMessageId?: string | null }) => void;
  stopStreaming: () => void;
  resetStream: () => void;
  setStreamingSources: (sources: SourcesData) => void;
}

export const useChatStore = create<ChatUIState>((set, get) => ({
  activeSessionId: undefined,
  streamingContent: '',
  isStreaming: false,
  abortStream: null,
  streamingSources: null,
  optimisticMessages: [],
  regeneratingMessageId: null,

  setActiveSession: (id) => {
    const { abortStream } = get();
    abortStream?.();
    set({
      activeSessionId: id,
      streamingContent: '',
      isStreaming: false,
      abortStream: null,
      streamingSources: null,
      optimisticMessages: [],
      regeneratingMessageId: null,
    });
  },

  addOptimisticUserMessage: (sessionId, content) => {
    const tempId = `temp-${Date.now()}`;
    set((s) => ({
      optimisticMessages: [
        ...s.optimisticMessages,
        {
          id: tempId,
          session_id: sessionId,
          role: 'user',
          content,
          created_at: new Date().toISOString(),
        },
      ],
    }));
    return tempId;
  },

  commitOptimisticUserMessage: (tempId, realId) =>
    set((s) => ({
      optimisticMessages: s.optimisticMessages.map((msg) =>
        msg.id === tempId ? { ...msg, id: realId } : msg,
      ),
    })),

  clearConfirmedOptimisticMessages: (messages) =>
    set((s) => ({
      optimisticMessages: s.optimisticMessages.filter(
        (msg) => !messages.some((serverMsg) => serverMsg.id === msg.id),
      ),
    })),

  clearOptimisticMessages: (sessionId) =>
    set((s) => ({
      optimisticMessages: sessionId
        ? s.optimisticMessages.filter((msg) => msg.session_id !== sessionId)
        : [],
    })),

  appendStreamToken: (token) =>
    set((s) => ({ streamingContent: s.streamingContent + token })),

  startStreaming: (abort, options) =>
    set({
      isStreaming: true,
      streamingContent: '',
      abortStream: abort,
      streamingSources: null,
      regeneratingMessageId: options?.regeneratingMessageId ?? null,
    }),

  stopStreaming: () =>
    set({ isStreaming: false, abortStream: null, regeneratingMessageId: null }),

  resetStream: () =>
    set({
      streamingContent: '',
      isStreaming: false,
      abortStream: null,
      streamingSources: null,
      optimisticMessages: [],
      regeneratingMessageId: null,
    }),

  setStreamingSources: (sources) =>
    set({ streamingSources: sources }),
}));
