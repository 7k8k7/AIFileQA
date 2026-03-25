import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ProviderConfig, ProviderTestResult } from '../../../types';
import SettingsPage from '../index';

const {
  useProvidersMock,
  useProviderMock,
  useCreateProviderMock,
  useUpdateProviderMock,
  useTestProviderMock,
  useSetDefaultProviderMock,
  useDeleteProviderMock,
} = vi.hoisted(() => ({
  useProvidersMock: vi.fn(),
  useProviderMock: vi.fn(),
  useCreateProviderMock: vi.fn(),
  useUpdateProviderMock: vi.fn(),
  useTestProviderMock: vi.fn(),
  useSetDefaultProviderMock: vi.fn(),
  useDeleteProviderMock: vi.fn(),
}));

vi.mock('../../../hooks', () => ({
  useProviders: useProvidersMock,
  useProvider: useProviderMock,
  useCreateProvider: useCreateProviderMock,
  useUpdateProvider: useUpdateProviderMock,
  useTestProvider: useTestProviderMock,
  useSetDefaultProvider: useSetDefaultProviderMock,
  useDeleteProvider: useDeleteProviderMock,
}));

const messageApi = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};

const provider: ProviderConfig = {
  id: 'provider-1',
  provider_type: 'openai',
  base_url: 'https://api.openai.com',
  model_name: 'gpt-4o',
  api_key: 'sk-test-1234',
  embedding_model: 'text-embedding-3-small',
  enable_embedding: true,
  temperature: 0.7,
  max_tokens: 4096,
  timeout_seconds: 30,
  is_default: true,
  last_test_success: true,
  last_test_message: '连接成功',
  last_test_at: '2026-03-25T10:00:00Z',
  created_at: '2026-03-25T10:00:00Z',
  updated_at: '2026-03-25T10:00:00Z',
};

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(App, 'useApp').mockReturnValue({ message: messageApi } as any);

    useProvidersMock.mockReturnValue({ data: [], isLoading: false });
    useProviderMock.mockReturnValue({ data: provider, isLoading: false });
    useCreateProviderMock.mockReturnValue({ mutate: vi.fn(), isPending: false });
    useUpdateProviderMock.mockReturnValue({ mutate: vi.fn(), isPending: false });
    useTestProviderMock.mockReturnValue({ mutate: vi.fn(), isPending: false });
    useSetDefaultProviderMock.mockReturnValue({ mutate: vi.fn(), isPending: false });
    useDeleteProviderMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
  });

  it('shows the empty state and opens the add-provider form', async () => {
    render(<SettingsPage />);

    expect(screen.getByText('还没有配置')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /添加供应商/ })[0]);

    expect(await screen.findByText('当前能力说明')).toBeInTheDocument();
    expect(screen.getByLabelText('Base URL')).toBeInTheDocument();
  });

  it('submits the add-provider form with the default openai values', async () => {
    const createMutate = vi.fn(
      (_payload: unknown, options?: { onSuccess?: () => void }) => {
        options?.onSuccess?.();
      },
    );
    useCreateProviderMock.mockReturnValue({ mutate: createMutate, isPending: false });

    render(<SettingsPage />);

    fireEvent.click(screen.getAllByRole('button', { name: /添加供应商/ })[0]);
    fireEvent.change(screen.getByPlaceholderText('sk-...'), {
      target: { value: 'sk-live-test' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: /添加供应商/ }).at(-1)!);

    await waitFor(() => {
      expect(createMutate).toHaveBeenCalledTimes(1);
    });

    expect(createMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        provider_type: 'openai',
        base_url: 'https://api.openai.com',
        model_name: 'gpt-4o',
        api_key: 'sk-live-test',
        embedding_model: 'text-embedding-3-small',
        enable_embedding: true,
        is_default: false,
      }),
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
    expect(messageApi.success).toHaveBeenCalledWith('供应商已添加');
  });

  it('switches provider defaults when the provider type changes to claude', async () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getAllByRole('button', { name: /添加供应商/ })[0]);

    const providerTypeSelect = screen.getAllByRole('combobox')[0];
    fireEvent.mouseDown(providerTypeSelect);
    fireEvent.click(await screen.findByText('Anthropic Claude'));

    await waitFor(() => {
      expect(screen.getByDisplayValue('https://api.anthropic.com')).toBeInTheDocument();
    });

    expect(screen.getByRole('switch')).toBeDisabled();
  });

  it('opens the edit form for an existing provider card', async () => {
    useProvidersMock.mockReturnValue({ data: [provider], isLoading: false });

    render(<SettingsPage />);

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[2]);

    expect(await screen.findByDisplayValue('https://api.openai.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('gpt-4o')).toBeInTheDocument();
  });

  it('disables deleting the default provider in the provider card', async () => {
    useProvidersMock.mockReturnValue({ data: [provider], isLoading: false });

    render(<SettingsPage />);

    const buttons = screen.getAllByRole('button');
    expect(buttons[buttons.length - 1]).toBeDisabled();
  });

  it('runs a provider connection test and shows the loading and success notifications', async () => {
    const testResult: ProviderTestResult = {
      success: true,
      message: 'ok',
      provider,
    };
    const testMutate = vi.fn(
      (_id: string, options?: { onSuccess?: (result: ProviderTestResult) => void }) => {
        options?.onSuccess?.(testResult);
      },
    );

    useProvidersMock.mockReturnValue({ data: [provider], isLoading: false });
    useTestProviderMock.mockReturnValue({ mutate: testMutate, isPending: false });

    render(<SettingsPage />);

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[1]);

    await waitFor(() => {
      expect(testMutate).toHaveBeenCalledWith(
        provider.id,
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        }),
      );
    });

    expect(messageApi.open).toHaveBeenCalledWith(
      expect.objectContaining({
        key: `provider-test-${provider.id}`,
        type: 'loading',
        content: '正在测试连接...',
        duration: 0,
      }),
    );
    expect(messageApi.open).toHaveBeenCalledWith(
      expect.objectContaining({
        key: `provider-test-${provider.id}`,
        type: 'success',
        content: '连接成功，已更新验证状态',
        duration: 2,
      }),
    );
  });
});
