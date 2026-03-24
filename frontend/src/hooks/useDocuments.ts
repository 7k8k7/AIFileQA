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
 * Auto-poll when any document is in '解析中' status.
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
      const hasParsing = query.state.data?.items.some(
        (d) => d.status === ('解析中' as DocumentStatus),
      );
      return hasParsing ? 3000 : false;
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
