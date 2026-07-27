# Agent-RAG Web

React + TypeScript + Tailwind v4 + Flowbite 前端，对接 FastAPI 后端。

## 启动

```bash
# 1. 先确保后端在跑（端口 8000）
cd ..  # 回到项目根
uv run uvicorn app.api.server:app --reload --port 8000

# 2. 启动前端（本目录）
cd web
npm install   # 首次
npm run dev   # 默认 http://localhost:5173
```

Vite 配置了 proxy，`/api` 自动转发到 `http://localhost:8000`，无跨域问题。

## 结构

```
src/
├── App.tsx              # 应用根（状态加载 + 布局）
├── main.tsx             # 入口
├── components/
│   ├── Sidebar.tsx      # 侧边栏：会话管理 + 文档上传 + 状态
│   ├── SourceList.tsx   # 引用来源折叠展示
│   └── ErrorBoundary.tsx
├── pages/Chat.tsx       # 主对话页（多轮 + 流式 + GSAP 动画）
├── hooks/useHashRoute.ts
├── lib/api.ts           # API 客户端（含 SSE 流式问答）
├── store.ts             # 极简会话 store（localStorage 持久化）
└── types/index.ts
```

## 构建

```bash
npm run build    # 输出到 dist/，可由 FastAPI 静态托管或 nginx 部署
```
