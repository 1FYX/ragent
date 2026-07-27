# Agent-RAG · 智能知识库问答

> 基于 **LangChain** 的 RAG 文档问答系统：上传文档 → 自动向量化 → 多轮对话式问答（带引用来源）。
>
> 前后端分离架构：FastAPI 后端 + React 前端，支持流式输出与多会话管理。

技术栈：Python · LangChain · 通义千问 · ChromaDB · FastAPI · React · TypeScript · Tailwind CSS

<!-- 演示截图：启动后截一张对话+引用展开的图，放到 docs/demo.png 并取消下行注释 -->
<!--
![demo](docs/demo.png)
-->

## ✨ 核心功能

- 📄 **多格式文档上传**：PDF / Markdown / TXT / DOCX，自动解析 + 递归切片 + 向量化入库
- 🔍 **语义检索**：基于通义 `text-embedding-v3` + ChromaDB，按「意思」而非「关键词」召回
- 💬 **多轮对话**：支持上下文追问（"那病假呢？"），每个会话独立历史
- 🌊 **流式输出**：SSE 流式回答，逐 token 显示
- 📎 **引用来源**：每条回答附带检索到的文档片段，可追溯
- 🔒 **去重入库**：基于内容 hash，同一文档重复上传不会污染向量库
- 🎨 **暗色科技风 UI**：React + Flowbite + GSAP 动画 + lucide 图标

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│  React 前端（端口 5173，dev）                                │
│  Vite + TypeScript + Tailwind v4 + Flowbite + GSAP          │
│  侧边栏（会话管理 + 上传）· 对话区（流式 + 引用 + 动画）     │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE（Vite proxy 转发 /api）
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI 后端（端口 8000）                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ /upload     │  │ /ask/stream │  │ /sessions/{id}/...  │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
└─────────┼─────────────────┼──────────────────────────────────┘
          │                 │
   ┌──────▼──────┐   ┌──────▼──────────────────────────────┐
   │  Loader     │   │  RAG Chain（LCEL 编排）              │
   │  + Splitter │   │  retriever | prompt(含历史) | llm    │
   └──────┬──────┘   └──┬───────────────┬───────────────────┘
          │             │               │
          │     ┌───────▼───────┐  ┌────▼──────┐
          │     │  ChromaDB     │  │ 通义千问  │
          │     │  (向量检索)   │  │ qwen-plus │
          │     └───────▲───────┘  └───────────┘
          │             │
   ┌──────▼──────┐ ┌────┴──────────────────┐
   │ Embedding  │ │ text-embedding-v3     │
   │ (入库)     │ │ (查询向量化 / 入库)   │
   └─────────────┘ └───────────────────────┘
```

## 🚀 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入通义千问 API Key：
#   DASHSCOPE_API_KEY=sk-你的key
# 申请地址：https://bailian.console.aliyun.com/
```

### 2. 启动后端（FastAPI，端口 8000）

```bash
uv run uvicorn app.api.server:app --reload --port 8000
```

### 3. 启动前端（React，端口 5173）

```bash
cd web
npm install        # 首次
npm run dev
```

打开 http://localhost:5173 → 左侧上传文档 → 提问。

> Vite 已配置 proxy，`/api` 自动转发到后端，无跨域问题。
> 如需快速体验，也可用 Streamlit 版本：`uv run streamlit run app/ui/app.py`（端口 8501）。

## 📂 项目结构

```
ragent/
├── app/                         # Python 后端
│   ├── api/server.py            # FastAPI：上传 / 对话 / 流式问答 / 会话历史
│   ├── rag/
│   │   ├── chain.py             # RAG 链核心（LCEL 编排 + 多轮历史）
│   │   └── loader.py            # 文档加载 + 递归切片
│   └── ui/app.py                # Streamlit 界面（备用）
├── web/                         # React 前端
│   └── src/
│       ├── App.tsx              # 应用根（状态加载 + 布局）
│       ├── components/
│       │   ├── Sidebar.tsx      # 侧边栏：会话管理 + 文档上传
│       │   ├── SourceList.tsx   # 引用来源折叠
│       │   └── ErrorBoundary.tsx
│       ├── pages/Chat.tsx       # 主对话页（多轮 + 流式 + GSAP 动画）
│       ├── lib/api.ts           # API 客户端（含 SSE 流式）
│       └── store.ts             # 会话 store（localStorage 持久化）
├── samples/                     # 测试文档（PDF/MD/TXT）
├── data/                        # 向量库 + 上传暂存（gitignore）
├── .env.example
└── pyproject.toml
```

## 🔌 API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/upload` | 上传文档（multipart，字段名 file） |
| POST | `/api/ask` | 非流式问答 |
| POST | `/api/ask/stream` | 流式问答（SSE） |
| GET  | `/api/sessions/{id}/history` | 读取会话历史 |
| DELETE | `/api/sessions/{id}/history` | 清空会话历史 |
| GET  | `/api/docs-count` | 向量库文档块数 |
| GET  | `/api/status` | 服务状态（key 配置 + 文档数） |
| GET  | `/api/docs` | Swagger 文档（FastAPI 自带） |

请求体示例：
```json
// POST /api/ask/stream
{
  "question": "工龄 5 年的员工有多少天年休假？",
  "k": 4,
  "session_id": "abc12345"
}
```

## 🔬 RAG 流程

```
上传文档
  → load_file         （PyPDF / Text / Markdown / DOCX Loader）
  → split_documents   （RecursiveCharacterTextSplitter，1000/200）
  → add_documents     （内容 hash 去重 → Chroma + Embedding）

提问（带 session_id）
  → 读取会话历史
  → retriever.invoke  （Chroma 相似度检索 top-k）
  → 拼 prompt         （system + 参考资料 + 历史消息 + 当前问题）
  → ChatOpenAI.stream （qwen-plus 流式生成）
  → 写入会话历史      （HumanMessage + AIMessage）
```

## 🛠️ 技术决策

| 决策 | 原因 |
|---|---|
| 通义千问（OpenAI 兼容模式） | 国内直连、有免费额度、chat + embedding 全能 |
| ChromaDB | 开发期零配置、本地持久化；生产可换 pgvector/Milvus |
| 自定义 DashscopeEmbeddings | 绕开 `langchain-openai` 新版与通义的 `contents` 字段不兼容问题 |
| InMemoryHistory | 简历项目聚焦 RAG；生产可换 Redis/SQLite 后端 |
| React + FastAPI 前后端分离 | 主界面用 React（精致可控），Streamlit 保留作快速演示备选 |
| Vite proxy `/api` | 开发期前后端分离但同源，零跨域配置 |
| Tailwind v4 + Flowbite | class-based dark mode（`@custom-variant`）+ Flowbite 主题插件 |

## 📝 License

MIT
