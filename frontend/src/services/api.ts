import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

export default api;

/**
 * SSE streaming via native fetch (axios does not support ReadableStream).
 * Returns an abort function.
 */
export function sseStream(
  path: string,
  body: unknown,
  callbacks: {
    onToken: (content: string) => void;
    onDone: (messageId: string) => void;
    onError: (error: Error) => void;
  },
): () => void {
  const baseURL = (import.meta.env.VITE_API_BASE_URL as string) ?? '/api';
  const controller = new AbortController();

  fetch(`${baseURL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const b = await res.json();
          detail = b.detail ?? detail;
        } catch { /* ignore */ }
        callbacks.onError(new Error(detail));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError(new Error('ReadableStream not supported'));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.type === 'token') {
              callbacks.onToken(data.content);
            } else if (data.type === 'done') {
              callbacks.onDone(data.message_id);
            } else if (data.type === 'error') {
              callbacks.onError(new Error(data.content));
            }
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError(err);
      }
    });

  return () => controller.abort();
}
