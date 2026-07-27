/**
 * 极简全局会话 store（不引入 zustand，避免依赖膨胀）。
 * 用模块级变量 + 订阅模式，足够本项目用。
 */
import { useSyncExternalStore } from 'react';

export interface Session {
  id: string;
  title: string;
  createdAt: number;
}

const STORAGE_KEY = 'ragent.sessions';
const CURRENT_KEY = 'ragent.current_session';

let sessions: Session[] = loadSessions();
let currentId: string | null = localStorage.getItem(CURRENT_KEY);
const listeners = new Set<() => void>();

function loadSessions(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  if (currentId) localStorage.setItem(CURRENT_KEY, currentId);
  else localStorage.removeItem(CURRENT_KEY);
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

export const sessionStore = {
  list(): Session[] {
    return sessions;
  },
  current(): Session | null {
    return sessions.find((s) => s.id === currentId) || null;
  },
  create(title = '新对话'): Session {
    const s: Session = { id: genId(), title, createdAt: Date.now() };
    sessions = [s, ...sessions];
    currentId = s.id;
    save();
    return s;
  },
  switchTo(id: string) {
    currentId = id;
    save();
  },
  rename(id: string, title: string) {
    sessions = sessions.map((s) => (s.id === id ? { ...s, title } : s));
    save();
  },
  remove(id: string) {
    sessions = sessions.filter((s) => s.id !== id);
    if (currentId === id) currentId = sessions[0]?.id ?? null;
    if (!currentId && sessions.length > 0) currentId = sessions[0].id;
    save();
  },
  /** 如果没有任何会话，自动建一个 */
  ensureOne(): Session {
    if (sessions.length === 0) return this.create();
    if (!currentId) {
      currentId = sessions[0].id;
      save();
    }
    return this.current()!;
  },
};

/** React hook：订阅会话列表变化 */
export function useSessions() {
  return useSyncExternalStore(subscribe, () => sessions);
}

/** React hook：订阅当前会话 id */
export function useCurrentSessionId() {
  return useSyncExternalStore(subscribe, () => currentId);
}
