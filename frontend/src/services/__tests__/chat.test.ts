import { beforeEach, describe, expect, it, vi } from 'vitest';

const sseStreamMock = vi.fn(() => vi.fn());

vi.mock('../api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
  sseStream: sseStreamMock,
}));

describe('chat service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sendMessage posts to correct URL', async () => {
    const { sendMessage } = await import('../chat');
    const callbacks = {
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
      onAccepted: vi.fn(),
      onSources: vi.fn(),
    };

    sendMessage('s-1', 'hello', callbacks);

    expect(sseStreamMock).toHaveBeenCalledWith(
      '/chat/sessions/s-1/messages',
      { content: 'hello' },
      callbacks,
    );
  });

  it('regenerateMessage posts to correct URL', async () => {
    const { regenerateMessage } = await import('../chat');
    const callbacks = {
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
      onAccepted: vi.fn(),
      onSources: vi.fn(),
    };

    regenerateMessage('s-1', 'm-1', callbacks);

    expect(sseStreamMock).toHaveBeenCalledWith(
      '/chat/sessions/s-1/messages/m-1/regenerate',
      {},
      callbacks,
    );
  });
});
