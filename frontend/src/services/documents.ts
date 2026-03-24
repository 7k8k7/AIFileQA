import type { Document, PaginatedResponse } from '../types';
import { mockDocuments } from './mock-data';

// ── Mock helpers ──

let docs = [...mockDocuments];
const delay = (ms = 300) => new Promise((r) => setTimeout(r, ms));

// ── API Functions ──

export async function fetchDocuments(params?: {
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Document>> {
  await delay();
  const { keyword = '', page = 1, page_size = 20 } = params ?? {};
  let filtered = docs;
  if (keyword) {
    const kw = keyword.toLowerCase();
    filtered = docs.filter((d) => d.file_name.toLowerCase().includes(kw));
  }
  const start = (page - 1) * page_size;
  return {
    items: filtered.slice(start, start + page_size),
    total: filtered.length,
    page,
    page_size,
  };
}

export async function fetchDocument(id: string): Promise<Document> {
  await delay();
  const doc = docs.find((d) => d.id === id);
  if (!doc) throw new Error('文档不存在');
  return doc;
}

export async function uploadDocument(file: File): Promise<Document> {
  await delay(500);
  const ext = '.' + file.name.split('.').pop()!.toLowerCase();
  const newDoc: Document = {
    id: `d-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    file_name: file.name,
    file_ext: ext,
    file_size: file.size,
    status: '解析中',
    uploaded_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  docs = [newDoc, ...docs];

  // Simulate parsing completion after 5s
  setTimeout(() => {
    const idx = docs.findIndex((d) => d.id === newDoc.id);
    if (idx !== -1) {
      docs[idx] = { ...docs[idx], status: '可用', updated_at: new Date().toISOString() };
    }
  }, 5000);

  return newDoc;
}

export async function deleteDocument(id: string): Promise<void> {
  await delay();
  docs = docs.filter((d) => d.id !== id);
}
