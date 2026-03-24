// ── Document ──

export type DocumentStatus = '上传中' | '解析中' | '可用' | '失败';

export interface Document {
  id: string;
  file_name: string;
  file_ext: string;
  file_size: number;
  status: DocumentStatus;
  error_message?: string;
  uploaded_at: string;
  updated_at: string;
}

// ── Chat ──

export type ScopeType = 'all' | 'single';

export interface ChatSession {
  id: string;
  title: string;
  scope_type: ScopeType;
  provider_id?: string;
  document_id?: string;
  document_ids: string[];
  created_at: string;
  updated_at: string;
}

export type MessageRole = 'user' | 'assistant';

export interface MessageSources {
  retrieval_method: string;
  chunks: SourceChunk[];
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  sources?: MessageSources | null;
  created_at: string;
}

// ── Provider ──

export type ProviderType = 'openai' | 'claude' | 'openai_compatible';

export interface ProviderConfig {
  id: string;
  provider_type: ProviderType;
  base_url: string;
  model_name: string;
  api_key: string; // masked from server
  embedding_model: string;
  enable_embedding: boolean;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
  is_default: boolean;
   last_test_success: boolean;
   last_test_message?: string | null;
   last_test_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderTestResult {
  success: boolean;
  message: string;
  provider: ProviderConfig;
}

// ── SSE ──

export interface SSETokenEvent {
  type: 'token';
  content: string;
}

export interface SSEDoneEvent {
  type: 'done';
  message_id: string;
}

export interface SourceChunk {
  document_name: string;
  chunk_index: number;
  content: string;
  page_no: number | null;
  score: number | null;
}

export interface SSESourcesEvent {
  type: 'sources';
  retrieval_method: string;
  chunks: SourceChunk[];
}

export type SSEEvent = SSETokenEvent | SSEDoneEvent | SSESourcesEvent;

// ── API ──

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
