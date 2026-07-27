"""
Streamlit UI：文档上传 + 多轮对话（带历史）+ 引用展示。

启动：streamlit run app/ui/app.py
"""
import json
import os
import uuid

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="LangChain RAG 知识库", page_icon="📚", layout="wide")


@st.cache_data(ttl=30)
def get_status() -> dict:
    try:
        r = requests.get(f"{API_URL}/api/status", timeout=5)
        return r.json() if r.ok else {"ok": False}
    except Exception:
        return {"ok": False}


def fetch_history(session_id: str) -> list[dict]:
    try:
        r = requests.get(f"{API_URL}/api/sessions/{session_id}/history", timeout=5)
        return r.json().get("messages", []) if r.ok else []
    except Exception:
        return []


def clear_history(session_id: str) -> bool:
    try:
        r = requests.delete(f"{API_URL}/api/sessions/{session_id}/history", timeout=5)
        return r.ok
    except Exception:
        return False


# —— 顶部标题 ——
st.title("📚 LangChain RAG 知识库")
st.caption("LangChain + ChromaDB · 上传文档 → 多轮提问")

status = get_status()
if not status.get("ok"):
    st.error("🔌 无法连接后端，请确认 FastAPI 已启动（端口 8000）")
    st.stop()

count = status.get("docs_count", 0)
key_ok = status.get("api_key_configured", False)

if not key_ok:
    st.warning(
        "⚠ **未配置 API Key**：服务已启动，界面可浏览，但上传/提问不可用。\n\n"
        "请编辑 `.env` 文件，填入 `DASHSCOPE_API_KEY`，保存后重启后端。"
    )

# —— 会话状态初始化 ——
if "sessions" not in st.session_state:
    # 会话列表：[{"id","title"}]
    st.session_state.sessions = []
    st.session_state.current_session = None


def new_session() -> str:
    sid = uuid.uuid4().hex[:8]
    st.session_state.sessions.append({"id": sid, "title": "新对话"})
    st.session_state.current_session = sid
    # 本会话的消息也缓存在前端，避免每次切回都重新加载（但首次切换会从后端拉）
    st.session_state[f"msgs_{sid}"] = []
    return sid


def switch_session(sid: str):
    st.session_state.current_session = sid
    # 若本地没有缓存，从后端拉历史
    if f"msgs_{sid}" not in st.session_state:
        st.session_state[f"msgs_{sid}"] = fetch_history(sid)


# 默认自动建一个会话
if not st.session_state.sessions:
    new_session()

current_sid = st.session_state.current_session

# —— 侧边栏 ——
with st.sidebar:
    st.metric("向量库文档块数", count)
    st.metric("API Key", "✅ 已配置" if key_ok else "❌ 未配置")

    st.divider()

    # 会话管理
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("➕ 新对话", use_container_width=True):
            new_session()
            st.rerun()
    with col2:
        if st.button("🗑", help="清空当前会话历史"):
            if clear_history(current_sid):
                st.session_state[f"msgs_{current_sid}"] = []
                st.rerun()

    st.write("**会话列表**")
    for s in st.session_state.sessions:
        is_cur = s["id"] == current_sid
        label = f"👉 {s['title']}" if is_cur else s["title"]
        if st.button(label, key=f"sess_{s['id']}", use_container_width=True):
            switch_session(s["id"])
            st.rerun()

    st.divider()

    # 上传区
    with st.expander("📤 上传文档", expanded=True):
        uploaded = st.file_uploader(
            "支持 PDF / TXT / MD / DOCX",
            type=["pdf", "txt", "md", "docx"],
        )
        if uploaded and st.button("上传并入库", use_container_width=True):
            with st.spinner("解析 + 切片 + 向量化中..."):
                try:
                    r = requests.post(
                        f"{API_URL}/api/upload",
                        files={"file": (uploaded.name, uploaded.getvalue())},
                        timeout=120,
                    )
                    if r.ok:
                        data = r.json()
                        st.success(
                            f"✅ {data['filename']}：新增 {data['chunks']} 块，"
                            f"总计 {data['total']} 块"
                        )
                        get_status.clear()
                        st.rerun()
                    else:
                        st.error(f"上传失败：{r.json().get('detail', r.text)}")
                except requests.ConnectionError:
                    st.error("无法连接后端，请确认 FastAPI 已启动")
                except Exception as e:
                    st.error(f"上传异常：{e}")

# —— 对话区 ——
msgs = st.session_state[f"msgs_{current_sid}"]

# 渲染历史
for msg in msgs:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📎 引用来源（{len(msg['sources'])}）"):
                for i, s in enumerate(msg["sources"], 1):
                    st.caption(f"[{i}] {s['content']}")

# 输入框
if question := st.chat_input("基于知识库提问...（支持多轮对话）"):
    if count == 0:
        st.warning("⚠ 向量库为空，请先在左侧上传文档。仍可提问但无 RAG 召回。")

    # 渲染用户消息
    msgs.append({"role": "user", "content": question})
    # 用问题前 20 字作会话标题（如果是第一条消息）
    if len(msgs) == 1:
        for s in st.session_state.sessions:
            if s["id"] == current_sid:
                s["title"] = question[:20] + ("..." if len(question) > 20 else "")
    with st.chat_message("user"):
        st.markdown(question)

    # 流式回答
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                resp = requests.post(
                    f"{API_URL}/api/ask/stream",
                    json={"question": question, "k": 4, "session_id": current_sid},
                    stream=True,
                    timeout=120,
                )
                if not resp.ok:
                    st.error(f"请求失败：HTTP {resp.status_code}")
                else:
                    full = ""
                    sources = []
                    placeholder = st.empty()
                    for line in resp.iter_lines(decode_unicode=True):
                        if not line or not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if "sources" in data:
                            sources = data["sources"]
                        elif "chunk" in data:
                            full += data["chunk"]
                            placeholder.markdown(full + "▌")
                        elif "error" in data:
                            st.error(f"⚠ {data['error']}")
                            full = f"⚠ {data['error']}"
                            break
                    placeholder.markdown(full)

                    msgs.append(
                        {"role": "assistant", "content": full, "sources": sources}
                    )
                    if sources:
                        with st.expander(f"📎 引用来源（{len(sources)}）"):
                            for i, s in enumerate(sources, 1):
                                st.caption(f"[{i}] {s['content']}")
            except requests.ConnectionError:
                st.error("无法连接后端，请确认 FastAPI 已启动")
            except Exception as e:
                st.error(f"异常：{e}")
