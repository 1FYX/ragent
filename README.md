# 📚 LangChain RAG 知识库

> 基于 **LangChain** 的 RAG 文档问答系统：上传文档 → 自动向量化 → 多轮对话式问答（带引用来源）。
>
> 技术栈：Python · LangChain · 通义千问 · ChromaDB · FastAPI · Streamlit

<!-- 演示截图占位：启动并测试后，截一张对话+引用展开的图，替换下面的路径 -->
<!--
![demo](docs/demo.png)
-->

## ✨ 核心功能

- 📄 **多格式文档上传**：PDF / Markdown / TXT / DOCX，自动解析 + 递归切片 + 向量化入库
- 🔍 **语义检索**：基于通义 `text-embedding-v3` + ChromaDB，按"意思"而非"关键词"召回
- 💬 **多轮对话**：支持上下文追问（"那病假呢？"），每个会话独立历史
- 🌊 **流式输出**：SSE 流式回答，逐 token 显示
- 📎 **引用来源**：每条回答附带检索到的文档片段，可追溯
- 🔒 **去重入库**：基于内容 hash，同一文档重复上传不会污染向量库

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│  Streamlit UI（端口 8501）                                  │
│  文档上传 · 会话管理 · 多轮对话 · 引用展示                  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI 后端（端口 8000）                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ /upload     │  │ /ask/stream │  │ /sessions/{id}/...  │ │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘ │
└─────────┼─────────────────┼────────────────────────────────┘
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

### 3. 启动 UI（Streamlit，端口 8501）

```bash
uv run streamlit run app/ui/app.py
```

打开 http://localhost:8501 → 左侧上传文档 → 提问。

## 📂 项目结构

```
langchain-rag/
├── app/
│   ├── api/server.py        # FastAPI：上传 / 对话 / 流式问答 / 会话历史
│   ├── rag/
│   │   ├── chain.py         # RAG 链核心（LCEL 编排 + 多轮历史）
│   │   └── loader.py        # 文档加载 + 递归切片
│   └── ui/app.py            # Streamlit 界面
├── samples/                 # 测试文档（PDF/MD/TXT）
├── data/                    # 向量库 + 上传暂存（gitignore）
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
| Streamlit | 单文件出完整 UI，适合原型与简历演示 |

## 📝 License

MIT
