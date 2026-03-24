import { create } from 'zustand';

interface ChatUIState {
  /** Currently active session ID */
  activeSessionId: string | undefined;
  /** Streaming assistant content being built up */
  streamingContent: string;
  /** Whether a stream is currently active */
  isStreaming: boolean;
  /** Abort function for the current stream */
  abortStream: (() => void) | null;

  setActiveSession: (id: string | undefined) => void;
  appendStreamToken: (token: string) => void;
  startStreaming: (abort: () => void) => void;
  stopStreaming: () => void;
  resetStream: () => void;
}

export const useChatStore = create<ChatUIState>((set, get) => ({
  activeSessionId: undefined,
  streamingContent: '',
  isStreaming: false,
  abortStream: null,

  setActiveSession: (id) => {
    const { abortStream } = get();
    abortStream?.();
    set({ activeSessionId: id, streamingContent: '', isStreaming: false, abortStream: null });
  },

  appendStreamToken: (token) =>
    set((s) => ({ streamingContent: s.streamingContent + token })),

  startStreaming: (abort) =>
    set({ isStreaming: true, streamingContent: '', abortStream: abort }),

  stopStreaming: () =>
    set({ isStreaming: false, abortStream: null }),

  resetStream: () =>
    set({ streamingContent: '', isStreaming: false, abortStream: null }),
}));
