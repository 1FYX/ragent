import { useState } from 'react';
import type { Source } from '../types';

/** 引用来源列表（可折叠）。展示检索到的文档片段，便于追溯。 */
export default function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-3 border-t border-slate-600/50 pt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200"
      >
        <span>{open ? '▾' : '▸'}</span>
        📎 引用来源（{sources.length}）
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <div
              key={i}
              className="rounded-md bg-slate-900/60 p-2 text-xs leading-relaxed text-slate-300"
            >
              <span className="mr-1 font-medium text-slate-500">[{i + 1}]</span>
              {s.content}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
