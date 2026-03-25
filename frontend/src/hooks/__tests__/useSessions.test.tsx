import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchSessionsMock = vi.fn();
const createSessionMock = vi.fn();
const updateSessionMock = vi.fn();
const deleteSessionMock = vi.fn();
const fetchMessagesMock = vi.fn();

vi.mock('../../services', () => ({
  fetchSessions: fetchSessionsMock,
  createSession: createSessionMock,
  updateSession: updateSessionMock,
  deleteSession: deleteSessionMock,
  fetchMessages: fetchMessagesMock,
}));

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useSessions hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useMessages stays idle when sessionId is missing', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    const { useMessages } = await import('../useSessions');
    const { result } = renderHook(() => useMessages(undefined), {
      wrapper: createWrapper(queryClient),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(fetchMessagesMock).not.toHaveBeenCalled();
  });

  it('useMessages fetches history when sessionId exists', async () => {
    fetchMessagesMock.mockResolvedValueOnce([{ id: 'm-1', role: 'user', content: 'hello' }]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    const { useMessages } = await import('../useSessions');
    const { result } = renderHook(() => useMessages('s-1'), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(fetchMessagesMock).toHaveBeenCalledWith('s-1');
    expect(result.current.data).toEqual([{ id: 'm-1', role: 'user', content: 'hello' }]);
  });

  it('useCreateSession invalidates sessions query after mutation', async () => {
    createSessionMock.mockResolvedValueOnce({ id: 's-1' });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { useCreateSession } = await import('../useSessions');
    const { result } = renderHook(() => useCreateSession(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ scope_type: 'all', provider_id: 'p-1' });
    });

    expect(createSessionMock).toHaveBeenCalledWith({ scope_type: 'all', provider_id: 'p-1' });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['sessions'] });
  });

  it('useInvalidateMessages targets the current session cache', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { useInvalidateMessages } = await import('../useSessions');
    const { result } = renderHook(() => useInvalidateMessages(), {
      wrapper: createWrapper(queryClient),
    });

    act(() => {
      result.current('s-42');
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['messages', 's-42'] });
  });
});
