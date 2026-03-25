import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatMessage, ChatSession, Document, ProviderConfig } from '../../../types';
import ChatPage from '../index';

const {
  useSessionsMock,
  useCreateSessionMock,
  useRenameSessionMock,
  useDeleteSessionMock,
  useMessagesMock,
  useInvalidateMessagesMock,
  useDocumentsMock,
  useProvidersMock,
  useChatStoreMock,
  sendMessageMock,
  regenerateMessageMock,
} = vi.hoisted(() => ({
  useSessionsMock: vi.fn(),
  useCreateSessionMock: vi.fn(),
  useRenameSessionMock: vi.fn(),
  useDeleteSessionMock: vi.fn(),
  useMessagesMock: vi.fn(),
  useInvalidateMessagesMock: vi.fn(),
  useDocumentsMock: vi.fn(),
  useProvidersMock: vi.fn(),
  useChatStoreMock: vi.fn(),
  sendMessageMock: vi.fn(),
  regenerateMessageMock: vi.fn(),
}));

vi.mock('../../../hooks', () => ({
  useSessions: useSessionsMock,
  useCreateSession: useCreateSessionMock,
  useRenameSession: useRenameSessionMock,
  useDeleteSession: useDeleteSessionMock,
  useMessages: useMessagesMock,
  useInvalidateMessages: useInvalidateMessagesMock,
  useDocuments: useDocumentsMock,
  useProviders: useProvidersMock,
}));

vi.mock('../../../services', () => ({
  sendMessage: sendMessageMock,
  regenerateMessage: regenerateMessageMock,
}));

vi.mock('../../../stores', () => ({
  useChatStore: useChatStoreMock,
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
  last_test_message: 'ok',
  last_test_at: '2026-03-25T10:00:00Z',
  created_at: '2026-03-25T10:00:00Z',
  updated_at: '2026-03-25T10:00:00Z',
};

const documents: Document[] = [
  {
    id: 'doc-1',
    file_name: '合同.pdf',
    file_ext: '.pdf',
    file_size: 1024,
    status: '可用',
    uploaded_at: '2026-03-25T10:00:00Z',
    updated_at: '2026-03-25T10:00:00Z',
  },
  {
    id: 'doc-2',
    file_name: 'FAQ.md',
    file_ext: '.md',
    file_size: 2048,
    status: '可用',
    uploaded_at: '2026-03-25T10:01:00Z',
    updated_at: '2026-03-25T10:01:00Z',
  },
];

const sessions: ChatSession[] = [
  {
    id: 'session-1',
    title: '第一轮对话',
    scope_type: 'single',
    provider_id: provider.id,
    document_id: documents[0].id,
    document_ids: documents.map((item) => item.id),
    created_at: '2026-03-25T10:00:00Z',
    updated_at: '2026-03-25T10:05:00Z',
  },
  {
    id: 'session-2',
    title: '第二轮对话',
    scope_type: 'all',
    provider_id: provider.id,
    document_ids: [],
    created_at: '2026-03-25T10:10:00Z',
    updated_at: '2026-03-25T10:12:00Z',
  },
];

function buildChatStore(overrides: Record<string, unknown> = {}) {
  return {
    activeSessionId: sessions[0].id,
    streamingContent: '',
    isStreaming: false,
    streamingSources: null,
    optimisticMessages: [],
    regeneratingMessageId: null,
    setActiveSession: vi.fn(),
    addOptimisticUserMessage: vi.fn(() => 'temp-user-1'),
    commitOptimisticUserMessage: vi.fn(),
    clearConfirmedOptimisticMessages: vi.fn(),
    clearOptimisticMessages: vi.fn(),
    appendStreamToken: vi.fn(),
    startStreaming: vi.fn(),
    stopStreaming: vi.fn(),
    setStreamingSources: vi.fn(),
    ...overrides,
  };
}

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(App, 'useApp').mockReturnValue({ message: messageApi } as any);

    useSessionsMock.mockReturnValue({ data: sessions, isLoading: false });
    useMessagesMock.mockReturnValue({ data: [], isLoading: false });
    useDocumentsMock.mockReturnValue({
      data: { items: documents, total: documents.length, page: 1, page_size: 20 },
    });
    useProvidersMock.mockReturnValue({ data: [provider] });
    useCreateSessionMock.mockReturnValue({ mutate: vi.fn(), isPending: false });
    useRenameSessionMock.mockReturnValue({ mutate: vi.fn(), isPending: false });
    useDeleteSessionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useInvalidateMessagesMock.mockReturnValue(vi.fn());
    useChatStoreMock.mockReturnValue(buildChatStore());
    sendMessageMock.mockReturnValue(vi.fn());
    regenerateMessageMock.mockReturnValue(vi.fn());
  });

  it('auto-selects the first session when the store has no active session yet', async () => {
    const store = buildChatStore({ activeSessionId: undefined });
    useChatStoreMock.mockReturnValue(store);

    render(<ChatPage />);

    await waitFor(() => {
      expect(store.setActiveSession).toHaveBeenCalledWith('session-1');
    });
  });

  it('sends a message from the composer and wires optimistic state to the stream callbacks', async () => {
    const abort = vi.fn();
    const invalidateMessages = vi.fn();
    const store = buildChatStore();

    useChatStoreMock.mockReturnValue(store);
    useInvalidateMessagesMock.mockReturnValue(invalidateMessages);
    sendMessageMock.mockImplementation(
      (_sessionId: string, _content: string, callbacks: { onAccepted?: (data: { userMessageId?: string }) => void }) => {
        callbacks.onAccepted?.({ userMessageId: 'user-message-1' });
        return abort;
      },
    );

    render(<ChatPage />);

    fireEvent.change(screen.getByPlaceholderText('输入您的问题...'), {
      target: { value: '总结一下这份合同' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'send' }));

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledTimes(1);
    });

    expect(store.addOptimisticUserMessage).toHaveBeenCalledWith('session-1', '总结一下这份合同');
    expect(sendMessageMock).toHaveBeenCalledWith(
      'session-1',
      '总结一下这份合同',
      expect.objectContaining({
        onToken: expect.any(Function),
        onDone: expect.any(Function),
        onError: expect.any(Function),
        onAccepted: expect.any(Function),
        onSources: expect.any(Function),
      }),
    );
    expect(store.commitOptimisticUserMessage).toHaveBeenCalledWith(
      'temp-user-1',
      'user-message-1',
    );
    expect(store.startStreaming).toHaveBeenCalledWith(abort);
  });

  it('opens the current provider settings modal from the chat header', async () => {
    useChatStoreMock.mockReturnValue(buildChatStore());

    render(<ChatPage />);

    fireEvent.click(screen.getByRole('button', { name: /查看设置/ }));

    expect(await screen.findByText('当前会话模型设置')).toBeInTheDocument();
    expect(screen.getByText('https://api.openai.com')).toBeInTheDocument();
    expect(screen.getByText('text-embedding-3-small')).toBeInTheDocument();
  });

  it('shows the scoped document list for single-document sessions', async () => {
    useChatStoreMock.mockReturnValue(buildChatStore());

    render(<ChatPage />);

    fireEvent.click(screen.getByRole('button', { name: /合同\.pdf 等2个文档/ }));

    expect(await screen.findByText('当前会话文档范围')).toBeInTheDocument();
    expect(screen.getByText('合同.pdf')).toBeInTheDocument();
    expect(screen.getByText('FAQ.md')).toBeInTheDocument();
  });

  it('only enables regenerate on the latest assistant message and calls the regenerate service', async () => {
    const abort = vi.fn();
    const store = buildChatStore();
    const messages: ChatMessage[] = [
      {
        id: 'msg-1',
        session_id: sessions[0].id,
        role: 'user',
        content: '你好',
        created_at: '2026-03-25T10:00:00Z',
      },
      {
        id: 'msg-2',
        session_id: sessions[0].id,
        role: 'assistant',
        content: '第一条回复',
        created_at: '2026-03-25T10:00:01Z',
      },
      {
        id: 'msg-3',
        session_id: sessions[0].id,
        role: 'assistant',
        content: '最新回复',
        created_at: '2026-03-25T10:00:02Z',
      },
    ];

    useChatStoreMock.mockReturnValue(store);
    useMessagesMock.mockReturnValue({ data: messages, isLoading: false });
    regenerateMessageMock.mockReturnValue(abort);

    render(<ChatPage />);

    const buttons = screen.getAllByRole('button', { name: /重新生成/ });
    expect(buttons[0]).toBeDisabled();
    expect(buttons[1]).toBeEnabled();

    fireEvent.click(buttons[1]);

    await waitFor(() => {
      expect(regenerateMessageMock).toHaveBeenCalledWith(
        'session-1',
        'msg-3',
        expect.objectContaining({
          onToken: expect.any(Function),
          onDone: expect.any(Function),
          onError: expect.any(Function),
          onSources: expect.any(Function),
        }),
      );
    });

    expect(store.startStreaming).toHaveBeenCalledWith(abort, {
      regeneratingMessageId: 'msg-3',
    });
  });
});
