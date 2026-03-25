import type { Document, PaginatedResponse } from '../types';
import api from './api';

const ALL_DOCUMENTS_PAGE_SIZE = 100;

export async function fetchDocuments(params?: {
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Document>> {
  const { data } = await api.get<PaginatedResponse<Document>>('/documents', { params });
  return data;
}

export async function fetchAllDocuments(params?: {
  keyword?: string;
}): Promise<Document[]> {
  const firstPage = await fetchDocuments({
    ...params,
    page: 1,
    page_size: ALL_DOCUMENTS_PAGE_SIZE,
  });

  if (firstPage.total <= firstPage.items.length) {
    return firstPage.items;
  }

  const totalPages = Math.ceil(firstPage.total / ALL_DOCUMENTS_PAGE_SIZE);
  const remainingPages = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) =>
      fetchDocuments({
        ...params,
        page: index + 2,
        page_size: ALL_DOCUMENTS_PAGE_SIZE,
      }),
    ),
  );

  return [firstPage, ...remainingPages].flatMap((page) => page.items);
}

export async function fetchDocument(id: string): Promise<Document> {
  const { data } = await api.get<Document>(`/documents/${id}`);
  return data;
}

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<Document>('/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`);
}
