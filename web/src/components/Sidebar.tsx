import { useRef, useState } from 'react';
import { Badge, Button } from 'flowbite-react';
import { Plus, Upload, Trash2, AlertTriangle } from 'lucide-react';
import { api } from '../lib/api';
import type { StatusResponse } from '../types';
import { sessionStore, useSessions, useCurrentSessionId } from '../store';

interface Props {
  status: StatusResponse;
  onStatusChange: () => void;
}

const ALLOWED_EXT = ['.pdf', '.txt', '.md', '.docx'];

export default function Sidebar({ status, onStatusChange }: Props) {
  const sessions = useSessions();
  const currentId = useCurrentSessionId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const handleNewSession = () => {
    sessionStore.create();
  };

  const handleSwitch = (id: string) => {
    sessionStore.switchTo(id);
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('删除这个会话？历史将丢失。')) return;
    sessionStore.remove(id);
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ''; // 允许重选同一文件
    setUploading(true);
    setUploadMsg(null);
    try {
      const r = await api.upload(file);
      setUploadMsg({
        type: 'ok',
        text: `✅ ${r.filename}：新增 ${r.chunks} 块，总计 ${r.total}`,
      });
      onStatusChange();
    } catch (err: any) {
      setUploadMsg({ type: 'err', text: err.message || '上传失败' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <aside className="flex w-72 flex-col border-r border-slate-700 bg-slate-800">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-slate-700 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 text-sm font-bold text-white shadow-lg">
          AR
        </div>
        <div>
          <div className="text-base font-semibold leading-tight text-slate-100">
            Agent-RAG
          </div>
          <div className="text-[11px] leading-tight text-slate-500">
            智能知识库问答
          </div>
        </div>
      </div>

      {/* 新建会话 */}
      <div className="p-3">
        <Button className="w-full" onClick={handleNewSession}>
          <Plus className="mr-1 h-4 w-4" /> 新建对话
        </Button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <div className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-slate-500">
          会话（{sessions.length}）
        </div>
        {sessions.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-slate-500">
            暂无会话，点击上方新建
          </p>
        ) : (
          <div className="space-y-1">
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSwitch(s.id)}
                className={`group flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  s.id === currentId
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                <span className="flex-1 truncate">{s.title}</span>
                <span
                  onClick={(e) => handleDelete(e, s.id)}
                  className={`ml-2 shrink-0 text-xs opacity-0 transition-opacity group-hover:opacity-100 ${
                    s.id === currentId ? 'text-blue-200' : 'text-red-400'
                  }`}
                  title="删除会话"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 文档上传 */}
      <div className="border-t border-slate-700 p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
            知识库
          </span>
          <Badge color={status.docs_count > 0 ? 'success' : 'gray'}>
            {status.docs_count} 块
          </Badge>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_EXT.join(',')}
          onChange={handleFile}
          className="hidden"
        />
        <Button
          color="gray"
          className="w-full border-slate-600 bg-slate-700 hover:bg-slate-600"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || !status.api_key_configured}
        >
          {uploading ? (
            '上传中...'
          ) : (
            <span className="flex items-center gap-1.5">
              <Upload className="h-4 w-4" /> 上传文档
            </span>
          )}
        </Button>

        {uploadMsg && (
          <div
            className={`mt-2 rounded-md p-2 text-xs ${
              uploadMsg.type === 'ok'
                ? 'bg-green-950/50 text-green-300'
                : 'bg-red-950/50 text-red-300'
            }`}
          >
            {uploadMsg.text}
          </div>
        )}

        <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
          支持 PDF / Markdown / TXT / DOCX，上传后自动切片入库。
        </p>

        {/* Key 状态 */}
        {!status.api_key_configured && (
          <div className="mt-3 flex items-start gap-1.5 rounded-md border border-amber-700 bg-amber-950/40 p-2 text-[11px] text-amber-300">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>未配置 API Key，请编辑后端 .env 填入 DASHSCOPE_API_KEY。</span>
          </div>
        )}
      </div>
    </aside>
  );
}
