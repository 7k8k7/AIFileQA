import { beforeEach, describe, expect, it } from 'vitest';
import { useChatStore } from '../chatStore';

const baseState = {
  activeSessionId: undefined,
  streamingContent: '',
  isStreaming: false,
  abortStream: null,
  streamingSources: null,
  optimisticMessages: [],
  regeneratingMessageId: null,
};

describe('chatStore', () => {
  beforeEach(() => {
    useChatStore.setState(baseState);
  });

  it('startStreaming sets isStreaming', () => {
    const abort = () => undefined;
    useChatStore.getState().startStreaming(abort);

    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().abortStream).toBe(abort);
  });

  it('appendStreamToken accumulates text', () => {
    useChatStore.getState().appendStreamToken('hello');
    useChatStore.getState().appendStreamToken(' world');

    expect(useChatStore.getState().streamingContent).toBe('hello world');
  });

  it('setStreamingSources stores sources', () => {
    useChatStore.getState().setStreamingSources({
      retrieval_method: 'vector',
      chunks: [{ document_name: 'a.txt', chunk_index: 0, content: 'alpha', page_no: 1, score: 0.9 }],
    });

    expect(useChatStore.getState().streamingSources?.retrieval_method).toBe('vector');
    expect(useChatStore.getState().streamingSources?.chunks).toHaveLength(1);
  });

  it('stopStreaming preserves sources', () => {
    useChatStore.getState().startStreaming(() => undefined);
    useChatStore.getState().setStreamingSources({
      retrieval_method: 'keyword',
      chunks: [{ document_name: 'b.txt', chunk_index: 0, content: 'beta', page_no: null, score: null }],
    });

    useChatStore.getState().stopStreaming();

    expect(useChatStore.getState().isStreaming).toBe(false);
    expect(useChatStore.getState().streamingSources?.chunks[0].document_name).toBe('b.txt');
  });

  it('addOptimisticUserMessage creates temp entry', () => {
    const tempId = useChatStore.getState().addOptimisticUserMessage('s-1', 'hello');

    expect(tempId.startsWith('temp-')).toBe(true);
    expect(useChatStore.getState().optimisticMessages).toEqual([
      expect.objectContaining({
        id: tempId,
        session_id: 's-1',
        role: 'user',
        content: 'hello',
      }),
    ]);
  });

  it('commitOptimisticUserMessage replaces temp', () => {
    const tempId = useChatStore.getState().addOptimisticUserMessage('s-1', 'hello');

    useChatStore.getState().commitOptimisticUserMessage(tempId, 'm-real');

    expect(useChatStore.getState().optimisticMessages[0].id).toBe('m-real');
  });
});
