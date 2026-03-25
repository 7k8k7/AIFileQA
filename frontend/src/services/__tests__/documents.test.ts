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

describe('documents service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetchDocuments forwards query params', async () => {
    const payload = {
      items: [{ id: 'doc-1', file_name: 'alpha.txt' }],
      total: 1,
      page: 1,
      page_size: 20,
    };
    mockApi.get.mockResolvedValueOnce({ data: payload });
    const { fetchDocuments } = await import('../documents');

    const result = await fetchDocuments({ keyword: 'alpha', page: 1, page_size: 20 });

    expect(mockApi.get).toHaveBeenCalledWith('/documents', {
      params: { keyword: 'alpha', page: 1, page_size: 20 },
    });
    expect(result).toEqual(payload);
  });

  it('fetchAllDocuments loads every page when the document list spans multiple pages', async () => {
    mockApi.get
      .mockResolvedValueOnce({
        data: {
          items: Array.from({ length: 100 }, (_, index) => ({ id: `doc-${index + 1}`, file_name: `doc-${index + 1}.txt` })),
          total: 120,
          page: 1,
          page_size: 100,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: Array.from({ length: 20 }, (_, index) => ({ id: `doc-${index + 101}`, file_name: `doc-${index + 101}.txt` })),
          total: 120,
          page: 2,
          page_size: 100,
        },
      });
    const { fetchAllDocuments } = await import('../documents');

    const result = await fetchAllDocuments();

    expect(mockApi.get).toHaveBeenNthCalledWith(1, '/documents', {
      params: { page: 1, page_size: 100 },
    });
    expect(mockApi.get).toHaveBeenNthCalledWith(2, '/documents', {
      params: { page: 2, page_size: 100 },
    });
    expect(result).toHaveLength(120);
    expect(result[0]).toMatchObject({ id: 'doc-1' });
    expect(result[119]).toMatchObject({ id: 'doc-120' });
  });

  it('fetchDocument reads detail endpoint', async () => {
    const payload = {
      id: 'doc-1',
      file_name: 'alpha.txt',
      file_ext: '.txt',
      file_size: 128,
      status: '可用',
      uploaded_at: '2026-03-25T12:00:00Z',
      updated_at: '2026-03-25T12:00:00Z',
    };
    mockApi.get.mockResolvedValueOnce({ data: payload });
    const { fetchDocument } = await import('../documents');

    const result = await fetchDocument('doc-1');

    expect(mockApi.get).toHaveBeenCalledWith('/documents/doc-1');
    expect(result).toEqual(payload);
  });

  it('uploadDocument sends multipart form data', async () => {
    mockApi.post.mockResolvedValueOnce({ data: { id: 'doc-1' } });
    const { uploadDocument } = await import('../documents');
    const file = new File(['hello'], 'sample.txt', { type: 'text/plain' });

    await uploadDocument(file);

    expect(mockApi.post).toHaveBeenCalledTimes(1);
    const [path, body, config] = mockApi.post.mock.calls[0];
    expect(path).toBe('/documents');
    expect(body).toBeInstanceOf(FormData);
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } });
  });

  it('deleteDocument sends delete request', async () => {
    mockApi.delete.mockResolvedValueOnce({});
    const { deleteDocument } = await import('../documents');

    await deleteDocument('doc-1');

    expect(mockApi.delete).toHaveBeenCalledWith('/documents/doc-1');
  });
});
