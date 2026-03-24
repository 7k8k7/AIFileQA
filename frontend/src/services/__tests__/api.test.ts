import { waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
};

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockApi),
  },
}));

describe('documents service and sseStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('fetchDocuments calls correct endpoint', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, page_size: 20 } });
    const { fetchDocuments } = await import('../documents');

    await fetchDocuments({ keyword: 'alpha', page: 1, page_size: 20 });

    expect(mockApi.get).toHaveBeenCalledWith('/documents', {
      params: { keyword: 'alpha', page: 1, page_size: 20 },
    });
  });

  it('uploadDocument sends FormData', async () => {
    mockApi.post.mockResolvedValueOnce({ data: { id: 'd-1' } });
    const { uploadDocument } = await import('../documents');
    const file = new File(['hello'], 'sample.txt', { type: 'text/plain' });

    await uploadDocument(file);

    expect(mockApi.post).toHaveBeenCalledTimes(1);
    const [path, body, config] = mockApi.post.mock.calls[0];
    expect(path).toBe('/documents');
    expect(body).toBeInstanceOf(FormData);
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } });
  });

  it('deleteDocument sends DELETE', async () => {
    mockApi.delete.mockResolvedValueOnce({});
    const { deleteDocument } = await import('../documents');

    await deleteDocument('d-1');

    expect(mockApi.delete).toHaveBeenCalledWith('/documents/d-1');
  });

  it('sseStream handles sources and token events', async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'data: {"type":"sources","retrieval_method":"keyword","chunks":[{"document_name":"a.txt","chunk_index":0,"content":"alpha","page_no":1,"score":1}]}\n\n',
      'data: {"type":"token","content":"hello"}\n\n',
      'data: {"type":"done","message_id":"m-1"}\n\n',
    ];

    const stream = new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'X-User-Message-Id': 'm-user-1' }),
      body: stream,
    });
    vi.stubGlobal('fetch', fetchMock);

    const { sseStream } = await import('../api');

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onSources = vi.fn();
    const onAccepted = vi.fn();
    const onError = vi.fn();

    sseStream('/chat/sessions/s-1/messages', { content: 'hello' }, {
      onToken,
      onDone,
      onSources,
      onAccepted,
      onError,
    });

    await waitFor(() => {
      expect(onDone).toHaveBeenCalledWith('m-1');
    });

    expect(fetchMock).toHaveBeenCalled();
    expect(onAccepted).toHaveBeenCalledWith({ userMessageId: 'm-user-1' });
    expect(onSources).toHaveBeenCalledWith({
      type: 'sources',
      retrieval_method: 'keyword',
      chunks: [{ document_name: 'a.txt', chunk_index: 0, content: 'alpha', page_no: 1, score: 1 }],
    });
    expect(onToken).toHaveBeenCalledWith('hello');
    expect(onError).not.toHaveBeenCalled();
  });
});
