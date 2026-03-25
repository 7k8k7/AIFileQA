import type { ProviderConfig } from '../../types';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type ProviderPayload = Omit<
  ProviderConfig,
  'id' | 'created_at' | 'updated_at' | 'last_test_success' | 'last_test_message' | 'last_test_at'
>;

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
};

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockApi),
  },
}));

describe('providers service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetchProviders reads provider list', async () => {
    mockApi.get.mockResolvedValueOnce({ data: [{ id: 'p-1' }] });
    const { fetchProviders } = await import('../providers');

    const result = await fetchProviders();

    expect(mockApi.get).toHaveBeenCalledWith('/providers');
    expect(result).toEqual([{ id: 'p-1' }]);
  });

  it('fetchProvider reads provider detail', async () => {
    mockApi.get.mockResolvedValueOnce({ data: { id: 'p-1' } });
    const { fetchProvider } = await import('../providers');

    const result = await fetchProvider('p-1');

    expect(mockApi.get).toHaveBeenCalledWith('/providers/p-1');
    expect(result).toEqual({ id: 'p-1' });
  });

  it('createProvider posts payload', async () => {
    const payload = {
      provider_type: 'openai',
      base_url: 'https://api.openai.com',
      model_name: 'gpt-4o-mini',
      api_key: 'sk-test',
      embedding_model: 'text-embedding-3-small',
      enable_embedding: true,
      temperature: 0.7,
      max_tokens: 512,
      timeout_seconds: 30,
      is_default: false,
    } satisfies ProviderPayload;
    mockApi.post.mockResolvedValueOnce({ data: { id: 'p-1', ...payload } });
    const { createProvider } = await import('../providers');

    const result = await createProvider(payload);

    expect(mockApi.post).toHaveBeenCalledWith('/providers', payload);
    expect(result).toMatchObject({ id: 'p-1', model_name: 'gpt-4o-mini' });
  });

  it('updateProvider sends PUT with partial payload', async () => {
    const payload = { model_name: 'gpt-4.1-mini', enable_embedding: false };
    mockApi.put.mockResolvedValueOnce({ data: { id: 'p-1', ...payload } });
    const { updateProvider } = await import('../providers');

    const result = await updateProvider('p-1', payload);

    expect(mockApi.put).toHaveBeenCalledWith('/providers/p-1', payload);
    expect(result).toMatchObject({ id: 'p-1', model_name: 'gpt-4.1-mini' });
  });

  it('testProvider hits test endpoint', async () => {
    mockApi.post.mockResolvedValueOnce({ data: { success: true } });
    const { testProvider } = await import('../providers');

    const result = await testProvider('p-1');

    expect(mockApi.post).toHaveBeenCalledWith('/providers/p-1/test');
    expect(result).toEqual({ success: true });
  });

  it('setDefaultProvider hits set-default endpoint', async () => {
    mockApi.post.mockResolvedValueOnce({});
    const { setDefaultProvider } = await import('../providers');

    await setDefaultProvider('p-1');

    expect(mockApi.post).toHaveBeenCalledWith('/providers/p-1/set-default');
  });

  it('deleteProvider hits delete endpoint', async () => {
    mockApi.delete.mockResolvedValueOnce({});
    const { deleteProvider } = await import('../providers');

    await deleteProvider('p-1');

    expect(mockApi.delete).toHaveBeenCalledWith('/providers/p-1');
  });
});
