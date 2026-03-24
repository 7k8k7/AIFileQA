import type { Document, PaginatedResponse } from '../types';
import api from './api';

export async function fetchDocuments(params?: {
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Document>> {
  const { data } = await api.get<PaginatedResponse<Document>>('/documents', { params });
  return data;
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
