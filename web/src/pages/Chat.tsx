import { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';
import { Alert, Spinner, Textarea } from 'flowbite-react';
import { api, streamAsk } from '../lib/api';
import type { ChatMessage, StatusResponse } from '../types';
import { sessionStore, useCurrentSessionId } from '../store';
import SourceList from '../components/SourceList';

gsap.registerPlugin(useGSAP);

interface Props {
  status: StatusResponse;
}

export default function ChatPage({ status }: Props) {
  const currentId = useCurrentSessionId();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  const messagesRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevCount = useRef(0);
  const abortRef = useRef<(() => void) | null>(null);

  // 确保至少有一个会话
  useEffect(() => {
    sessionStore.ensureOne();
  }, []);

  // 切换会话 → 加载历史
  useEffect(() => {
    if (!currentId) {
      setMessages([]);
      return;
    }
    setLoadingHistory(true);
    setError('');
    api
      .getHistory(currentId)
      .then((r) => {
        setMessages(
          r.messages.map((m, i) => ({
            id: `${currentId}-${i}`,
            role: m.role,
            content: m.content,
          })),
        );
        prevCount.current = r.messages.length;
      })
      .catch(() => setMessages([]))
      .finally(() => setLoadingHistory(false));
  }, [currentId]);

  // 滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 新消息滑入动画（只对增量）
  useEffect(() => {
    const nodes = messagesRef.current?.querySelectorAll('[data-msg]');
    if (!nodes || nodes.length === 0) return;
    const newOnes = Array.from(nodes).slice(prevCount.current);
    if (newOnes.length > 0) {
      gsap.from(newOnes, {
        opacity: 0,
        y: 12,
        duration: 0.3,
        ease: 'power2.out',
        stagger: 0.04,
      });
    }
    prevCount.current = nodes.length;
  }, [messages]);

  const send = () => {
    const q = input.trim();
    if (!q || sending) return;
    if (!currentId) return;

    setInput('');
    setSending(true);
    setError('');

    // 用问题前 20 字更新会话标题（仅首次）
    if (messages.length === 0) {
      sessionStore.rename(currentId, q.slice(0, 20) + (q.length > 20 ? '...' : ''));
    }

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: q,
    };
    const aiId = `a-${Date.now()}`;
    const aiMsg: ChatMessage = {
      id: aiId,
      role: 'assistant',
      content: '',
      pending: true,
    };
    setMessages((prev) => [...prev, userMsg, aiMsg]);

    abortRef.current = streamAsk(
      q,
      {
        onSources: (sources) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === aiId ? { ...m, sources } : m)),
          );
        },
        onChunk: (chunk) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiId
                ? { ...m, content: m.content + chunk, pending: false }
                : m,
            ),
          );
        },
        onDone: () => {
          setSending(false);
        },
        onError: (msg) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiId
                ? { ...m, content: `⚠ ${msg}`, pending: false, isError: true }
                : m,
            ),
          );
          setSending(false);
        },
      },
      currentId,
    );
  };

  return (
    <div className="flex h-full flex-col">
      {/* 顶部状态条 */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-700 bg-slate-800/50 px-6">
        <div className="text-sm font-medium text-slate-300">
          {sessionStore.current()?.title || 'Agent-RAG'}
        </div>
        <div className="text-xs text-slate-500">
          {status.docs_count === 0
            ? '⚠ 知识库为空，将无 RAG 召回'
            : `📚 ${status.docs_count} 个文档块可检索`}
        </div>
      </div>

      {/* 消息区 */}
      <div ref={messagesRef} className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-5">
          {loadingHistory ? (
            <div className="flex justify-center py-10">
              <Spinner size="lg" />
            </div>
          ) : messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((m) => <MessageBubble key={m.id} msg={m} />)
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="px-6">
          <Alert color="failure" className="mx-auto max-w-3xl">
            {error}
          </Alert>
        </div>
      )}

      {/* 输入区 */}
      <div className="shrink-0 border-t border-slate-700 bg-slate-800/50 px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-end gap-3">
          <Textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={
              status.api_key_configured
                ? '基于知识库提问...（Enter 发送，Shift+Enter 换行）'
                : '请先在后端配置 API Key'
            }
            disabled={sending || !status.api_key_configured}
            className="flex-1 resize-none border-slate-600 bg-slate-900"
          />
          <button
            onClick={send}
            disabled={sending || !input.trim() || !status.api_key_configured}
            className="h-11 shrink-0 rounded-xl bg-blue-600 px-5 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending ? '回答中...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}

/** 单条消息气泡 */
function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div data-msg className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex max-w-[80%] gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* 头像 */}
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            isUser ? 'bg-blue-600 text-white' : 'bg-purple-600 text-white'
          }`}
        >
          {isUser ? '我' : 'AI'}
        </div>
        {/* 气泡 */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            msg.isError
              ? 'border border-red-800 bg-red-950/50 text-red-200'
              : isUser
                ? 'rounded-tr-sm bg-blue-600 text-white'
                : 'rounded-tl-sm bg-slate-800 text-slate-100'
          }`}
        >
          {msg.content ? (
            <div className="whitespace-pre-wrap">{msg.content}</div>
          ) : msg.pending ? (
            <div className="flex items-center gap-2 text-slate-400">
              <Spinner size="sm" /> 思考中...
            </div>
          ) : null}

          {/* 引用来源 */}
          {msg.sources && msg.sources.length > 0 && !msg.pending && (
            <SourceList sources={msg.sources} />
          )}
        </div>
      </div>
    </div>
  );
}

/** 空状态 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 text-2xl">
        💬
      </div>
      <h3 className="mb-2 text-lg font-semibold text-slate-200">
        开始与知识库对话
      </h3>
      <p className="max-w-md text-sm text-slate-400">
        先在左侧上传文档（PDF/MD/TXT/DOCX），然后在这里提问。
        支持多轮对话，可基于上下文追问。
      </p>
    </div>
  );
}
