import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Document } from '../../../types';
import DocumentsPage from '../index';

const {
  useDocumentsWithPollingMock,
  uploadMutateMock,
  deleteMutateAsyncMock,
} = vi.hoisted(() => ({
  useDocumentsWithPollingMock: vi.fn(),
  uploadMutateMock: vi.fn(),
  deleteMutateAsyncMock: vi.fn(),
}));

vi.mock('../../../hooks', () => ({
  useDocumentsWithPolling: useDocumentsWithPollingMock,
  useUploadDocument: () => ({ mutate: uploadMutateMock }),
  useDeleteDocument: () => ({ mutateAsync: deleteMutateAsyncMock }),
}));

const messageApi = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};

const baseDocument: Document = {
  id: 'doc-1',
  file_name: '需求说明.md',
  file_ext: '.md',
  file_size: 2048,
  status: '可用',
  uploaded_at: '2026-03-25T10:00:00Z',
  updated_at: '2026-03-25T10:00:00Z',
};

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(App, 'useApp').mockReturnValue({ message: messageApi } as any);
    useDocumentsWithPollingMock.mockReturnValue({
      data: { items: [baseDocument], total: 1, page: 1, page_size: 20 },
      isLoading: false,
    });
    uploadMutateMock.mockImplementation((_file: File, options?: { onSuccess?: () => void }) => {
      options?.onSuccess?.();
    });
    deleteMutateAsyncMock.mockResolvedValue(undefined);
  });

  it('renders the empty state upload call to action when there are no documents', () => {
    useDocumentsWithPollingMock.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
    });

    render(<DocumentsPage />);

    expect(screen.getByText('还没有文档')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /上传文档/ })).toBeInTheDocument();
  });

  it('shows a loading skeleton while the initial list is loading', () => {
    useDocumentsWithPollingMock.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    const { container } = render(<DocumentsPage />);

    expect(screen.getByText('文档管理')).toBeInTheDocument();
    expect(container.querySelector('.ant-skeleton')).not.toBeNull();
  });

  it('uploads a file from the empty state and reports success', async () => {
    useDocumentsWithPollingMock.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
    });

    render(<DocumentsPage />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).not.toBeNull();

    const file = new File(['hello world'], 'notes.md', { type: 'text/markdown' });
    fireEvent.change(input!, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadMutateMock).toHaveBeenCalledTimes(1);
    });

    expect(uploadMutateMock).toHaveBeenCalledWith(
      file,
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
    expect(messageApi.success).toHaveBeenCalledWith(
      'notes.md 上传成功，系统正在解析，完成后即可用于问答',
    );
  });

  it('rejects oversized uploads before calling the mutation', async () => {
    useDocumentsWithPollingMock.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
    });

    render(<DocumentsPage />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement | null;
    expect(input).not.toBeNull();

    const file = new File(['x'], 'too-large.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: 51 * 1024 * 1024 });

    fireEvent.change(input!, { target: { files: [file] } });

    await waitFor(() => {
      expect(messageApi.error).toHaveBeenCalledWith('文件 too-large.pdf 超过 50MB 限制');
    });

    expect(uploadMutateMock).not.toHaveBeenCalled();
  });

  it('updates the polling query when the keyword changes and shows the search empty state', async () => {
    useDocumentsWithPollingMock.mockImplementation(
      ({ keyword = '', page = 1, page_size = 20 }: { keyword?: string; page?: number; page_size?: number }) => ({
        data:
          keyword === 'missing'
            ? { items: [], total: 0, page, page_size }
            : { items: [baseDocument], total: 1, page, page_size },
        isLoading: false,
      }),
    );

    render(<DocumentsPage />);

    fireEvent.change(screen.getByPlaceholderText('搜索文档名称...'), {
      target: { value: 'missing' },
    });

    await waitFor(() => {
      expect(useDocumentsWithPollingMock).toHaveBeenLastCalledWith({
        keyword: 'missing',
        page: 1,
        page_size: 20,
      });
    });

    expect(screen.getByText('没有匹配的文档')).toBeInTheDocument();
  });
});
