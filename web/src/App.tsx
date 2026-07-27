import { useEffect, useState } from 'react';
import { Spinner } from 'flowbite-react';
import { api } from './lib/api';
import type { StatusResponse } from './types';
import { ErrorBoundary } from './components/ErrorBoundary';
import Sidebar from './components/Sidebar';
import ChatPage from './pages/Chat';

export default function App() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshStatus = () => {
    api
      .status()
      .then(setStatus)
      .catch(() => setStatus({ ok: false, api_key_configured: false, docs_count: 0 }))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refreshStatus();
    // 每 30s 轮询一次，让 docs_count 自动更新（上传/清空后能感知）
    const t = setInterval(refreshStatus, 30000);
    return () => clearInterval(t);
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900">
        <Spinner size="xl" />
      </div>
    );
  }

  // 后端连不上
  if (!status?.ok) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 p-6">
        <div className="max-w-md rounded-2xl border border-red-800 bg-slate-800 p-6 text-center">
          <h2 className="mb-2 text-lg font-bold text-red-400">🔌 无法连接后端</h2>
          <p className="text-sm text-slate-300">
            请确认 FastAPI 已启动：
            <code className="mx-1 rounded bg-slate-950 px-2 py-0.5 text-xs">
              uv run uvicorn app.api.server:app --port 8000
            </code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-slate-900 text-slate-100">
        <Sidebar status={status} onStatusChange={refreshStatus} />
        <main className="flex-1 overflow-hidden">
          <ChatPage status={status} />
        </main>
      </div>
    </ErrorBoundary>
  );
}
