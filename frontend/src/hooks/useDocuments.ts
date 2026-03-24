import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchDocuments, uploadDocument, deleteDocument } from '../services';
import type { DocumentStatus } from '../types';

const DOCS_KEY = ['documents'] as const;

export function useDocuments(params?: {
  keyword?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: [...DOCS_KEY, params],
    queryFn: () => fetchDocuments(params),
  });
}

/**
 * Auto-poll when any document is still in the upload/parse pipeline.
 */
export function useDocumentsWithPolling(params?: {
  keyword?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: [...DOCS_KEY, params],
    queryFn: () => fetchDocuments(params),
    refetchInterval: (query) => {
      const hasPending = query.state.data?.items.some(
        (d) => ['上传中', '解析中'].includes(d.status as DocumentStatus),
      );
      return hasPending ? 3000 : false;
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: DOCS_KEY }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: DOCS_KEY }),
  });
}
