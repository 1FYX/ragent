"""
FastAPI 后端：文档上传 + RAG 问答（含流式）。

接口：
- POST /api/upload      上传文档（PDF/TXT/MD/DOCX），自动切片入向量库
- POST /api/ask         非流式问答
- POST /api/ask/stream  流式问答（SSE）
- GET  /api/health      健康检查
- GET  /api/docs-count  查看向量库文档数

简化说明：本项目聚焦 RAG 本身，不做用户认证/多租户/权限。
"""
import json
import shutil
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.rag.chain import RAGChain, is_api_key_configured
from app.rag.loader import load_and_split

app = FastAPI(title="LangChain RAG", version="0.1.0")

# 未配置 key 时的统一提示
NO_KEY_MSG = (
    "未配置 LLM_API_KEY，RAG 功能不可用。"
    "请复制 .env.example 为 .env，填入你的 LLM API Key。"
)

# 允许前端跨域调用（Streamlit 8501 / React dev 5173 / 生产构建）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 把 uploads 目录挂为静态文件，前端可直接访问 /uploads/文件名 下载原文
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 单例 RAG 链（向量库复用）
_rag: RAGChain | None = None


def get_rag() -> RAGChain:
    global _rag
    if _rag is None:
        _rag = RAGChain()
    return _rag


ALLOWED_EXT = {".pdf", ".txt", ".md", ".docx"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def status():
    """返回服务状态 + key 配置情况（UI 据此显示提示）。"""
    return {
        "ok": True,
        "api_key_configured": is_api_key_configured(),
        "docs_count": _safe_docs_count(),
    }


def _safe_docs_count() -> int:
    """安全读取文档数：没 key 或向量库未初始化时返回 0。"""
    if not is_api_key_configured() or _rag is None:
        return 0
    try:
        return _rag._vectorstore._collection.count()
    except Exception:
        return 0


@app.get("/api/docs-count")
def docs_count():
    """返回向量库当前文档块数量。"""
    if not is_api_key_configured():
        raise HTTPException(400, NO_KEY_MSG)
    rag = get_rag()
    # Chroma 没有 len()，用 collection.count()
    count = rag._vectorstore._collection.count()
    return {"count": count}


@app.get("/api/documents")
def list_documents():
    """返回已上传文档列表（按文件名聚合）。"""
    if not is_api_key_configured():
        raise HTTPException(400, NO_KEY_MSG)
    rag = get_rag()
    return {"documents": rag.list_documents()}


@app.delete("/api/documents")
def delete_document(source: str):
    """按 source 删除某文档的所有向量。?source=文件路径"""
    if not is_api_key_configured():
        raise HTTPException(400, NO_KEY_MSG)
    rag = get_rag()
    deleted = rag.delete_document(source)
    return {"deleted": deleted, "remaining": rag._vectorstore._collection.count()}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """上传文档 → 切片 → 入向量库。"""
    if not is_api_key_configured():
        raise HTTPException(400, NO_KEY_MSG)
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"仅支持 {ALLOWED_EXT}，收到 {ext}")

    # 落盘
    save_path = UPLOAD_DIR / f"{file.filename}"
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # 加载 + 切片
        chunks = load_and_split(str(save_path))
        if not chunks:
            raise HTTPException(400, "解析得到空内容（可能是扫描版 PDF 或空文件）")

        # 统一 source 为纯文件名（便于后续按文件聚合 + 提供 downloads）
        for c in chunks:
            c.metadata["source"] = file.filename

        # 入库
        rag = get_rag()
        n = rag.add_documents(chunks)

        return {
            "filename": file.filename,
            "chunks": n,
            "total": rag._vectorstore._collection.count(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"处理失败：{e}")


@app.post("/api/ask")
async def ask(body: dict):
    """非流式问答。body: {"question": "...", "k": 4, "session_id": "..."}"""
    if not is_api_key_configured():
        raise HTTPException(400, NO_KEY_MSG)
    question = (body or {}).get("question", "").strip()
    if not question:
        raise HTTPException(400, "question 不能为空")
    k = (body or {}).get("k", 4)
    session_id = (body or {}).get("session_id")

    try:
        rag = get_rag()
        answer, sources = rag.ask(question, k=k, session_id=session_id)
        return {
            "answer": answer,
            "sources": [
                {"content": s.page_content[:200], "metadata": s.metadata}
                for s in sources
            ],
        }
    except Exception as e:
        raise HTTPException(500, f"问答失败：{e}")


@app.post("/api/ask/stream")
async def ask_stream(body: dict):
    """流式问答（SSE）。body: {"question": "...", "k": 4, "session_id": "..."}"""
    if not is_api_key_configured():
        raise HTTPException(400, NO_KEY_MSG)
    question = (body or {}).get("question", "").strip()
    if not question:
        raise HTTPException(400, "question 不能为空")
    k = (body or {}).get("k", 4)
    session_id = (body or {}).get("session_id")

    rag = get_rag()

    def gen():
        try:
            stream = rag.ask_stream(question, k=k, session_id=session_id)
            # 第一个 yield 是引用来源列表
            sources = next(stream)
            yield f"data: {json.dumps({'sources': [{'content': s.page_content[:200]} for s in sources]}, ensure_ascii=False)}\n\n"
            # 后续 yield 是文本 chunk
            for chunk in stream:
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/sessions/{session_id}/history")
def get_history(session_id: str):
    """读取某会话的历史消息。"""
    rag = get_rag()
    return {"messages": rag.get_history_messages(session_id)}


@app.delete("/api/sessions/{session_id}/history")
def clear_history(session_id: str):
    """清空某会话的历史。"""
    rag = get_rag()
    rag.clear_history(session_id)
    return {"ok": True}


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "app.api.server:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
