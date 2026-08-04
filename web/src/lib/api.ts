import type {
  StatusResponse,
  UploadResponse,
  AskResponse,
  HistoryMessage,
  Source,
} from '../types';

const API_BASE = '/api';

// —— 通用请求封装 ——
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch {
    throw new Error('无法连接服务器，请确认 FastAPI 已启动（端口 8000）');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(data?.detail || `请求失败（HTTP ${res.status}）`);
  }
  return data as T;
}

// —— 接口定义 ——
export const api = {
  /** 服务状态 */
  status: () => request<StatusResponse>('/status'),

  /** 上传文档（multipart） */
  upload: async (file: File): Promise<UploadResponse> => {
    const fd = new FormData();
    fd.append('file', file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: fd });
    } catch {
      throw new Error('上传失败：无法连接服务器');
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail || `上传失败（HTTP ${res.status}）`);
    return data as UploadResponse;
  },

  /** 非流式问答 */
  ask: (question: string, sessionId?: string, k = 4) =>
    request<AskResponse>('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, k, session_id: sessionId }),
    }),

  /** 读取会话历史 */
  getHistory: (sessionId: string) =>
    request<{ messages: HistoryMessage[] }>(`/sessions/${sessionId}/history`),

  /** 清空会话历史 */
  clearHistory: (sessionId: string) =>
    request<{ ok: boolean }>(`/sessions/${sessionId}/history`, { method: 'DELETE' }),

  /** 文档块数 */
  docsCount: () => request<{ count: number }>('/docs-count'),

  /** 已上传文档列表 */
  listDocuments: () =>
    request<{ documents: Array<{ source: string; name: string; chunks: number; preview: string }> }>(
      '/documents',
    ),

  /** 删除某文档（按 source） */
  deleteDocument: (source: string) =>
    request<{ deleted: number; remaining: number }>(
      `/documents?source=${encodeURIComponent(source)}`,
      { method: 'DELETE' },
    ),
};

/**
 * 流式问答（SSE over POST）。
 * 返回一个 abort 函数，调用方用于中断。
 *
 * 浏览器 EventSource 不支持 POST + 自定义 header，这里手写 fetch 流式读取，
 * 与后端的 SSE 帧格式（`data: {...}\n\n`）匹配。
 */
export function streamAsk(
  question: string,
  handlers: {
    onSources?: (sources: Source[]) => void;
    onChunk: (chunk: string) => void;
    onDone?: () => void;
    onError?: (msg: string) => void;
  },
  sessionId?: string,
  k = 4,
): () => void {
  const controller = new AbortController();

  (async () => {
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, k, session_id: sessionId }),
        signal: controller.signal,
      });
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        handlers.onError?.('无法连接服务器，请确认 FastAPI 已启动');
      }
      return;
    }

    if (!res.ok || !res.body) {
      let msg = `请求失败（HTTP ${res.status}）`;
      try {
        const d = await res.json();
        if (d?.detail) msg = d.detail;
      } catch {}
      handlers.onError?.(msg);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const line = frame.split('\n').find((l) => l.startsWith('data: '));
        if (!line) continue;
        const payload = line.slice(6);
        if (payload === '[DONE]') {
          handlers.onDone?.();
          return;
        }
        try {
          const data = JSON.parse(payload);
          if (data.sources) handlers.onSources?.(data.sources);
          if (data.chunk) handlers.onChunk?.(data.chunk);
          if (data.error) handlers.onError?.(data.error);
        } catch {
          /* 忽略无法解析的帧 */
        }
      }
    }
    handlers.onDone?.();
  })();

  return () => controller.abort();
}
