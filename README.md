# LangChain RAG 知识库

> 基于 **LangChain** 的 RAG 问答系统:上传文档 → 自动向量化 → 基于文档提问。
> 技术栈:Python + LangChain + 通义千问 + ChromaDB + FastAPI + Streamlit。

## 技术栈

| 层 | 技术 |
|---|---|
| RAG 框架 | LangChain(LCEL 链式编排) |
| LLM / Embedding | 通义千问(OpenAI 兼容模式):`qwen-plus` + `text-embedding-v3` |
| 向量库 | ChromaDB(本地持久化,零配置) |
| 后端 | FastAPI |
| UI | Streamlit |
| 包管理 | uv |

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入通义千问 API Key
#   DASHSCOPE_API_KEY=sk-你的key
# 申请地址：https://bailian.console.aliyun.com/
```

### 2. 启动后端(FastAPI,端口 8000)

```bash
uv run uvicorn app.api.server:app --reload --port 8000
```

### 3. 启动 UI(Streamlit,端口 8501)

```bash
uv run streamlit run app/ui/app.py
```

打开 http://localhost:8501 → 左侧上传文档 → 输入框提问。

## 项目结构

```
langchain-rag/
├── app/
│   ├── api/server.py        # FastAPI：上传/对话/流式问答
│   ├── rag/
│   │   ├── chain.py         # RAG 链核心（LCEL 编排）
│   │   └── loader.py        # 文档加载 + 切片
│   └── ui/app.py            # Streamlit 界面
├── data/
│   ├── chroma/              # 向量库持久化（gitignore）
│   └── uploads/             # 上传文件暂存（gitignore）
├── .env.example
├── pyproject.toml
└── README.md
```

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/upload` | 上传文档(multipart,字段名 file) |
| POST | `/api/ask` | 非流式问答 |
| POST | `/api/ask/stream` | 流式问答(SSE) |
| GET | `/api/docs-count` | 向量库文档块数 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/docs` | Swagger 文档(FastAPI 自带) |

## RAG 流程

```
上传文档
  → load_file        (PyPDF/Text/Markdown Loader)
  → split_documents  (RecursiveCharacterTextSplitter,1000/200)
  → add_documents    (Chroma + OpenAIEmbeddings)

提问
  → as_retriever.invoke     (Chroma 相似度检索 top-k)
  → format_docs + RAG_PROMPT (拼引用上下文)
  → ChatOpenAI.stream        (qwen-plus 流式生成)
```
