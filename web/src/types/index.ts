export interface StatusResponse {
  ok: boolean;
  api_key_configured: boolean;
  docs_count: number;
}

export interface UploadResponse {
  filename: string;
  chunks: number;
  total: number;
}

export interface Source {
  content: string;
  metadata?: Record<string, unknown>;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

/** 前端会话内的消息（含流式追加用的额外字段） */
export interface ChatMessage extends HistoryMessage {
  id: string;
  sources?: Source[];
  /** 流式输出进行中 */
  pending?: boolean;
  /** 出错消息（红色气泡） */
  isError?: boolean;
}
