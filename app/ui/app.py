"""
Streamlit UI：一个文件出完整界面（文档上传 + 对话 + 引用展示）。

启动：streamlit run app/ui/app.py
API 地址默认 http://localhost:8000，通过环境变量 API_URL 覆盖。
"""
import json
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="LangChain RAG 知识库", page_icon="📚", layout="wide")


@st.cache_data(ttl=30)
def get_status() -> dict:
    """获取后端状态：key 是否配置 + 文档数。"""
    try:
        r = requests.get(f"{API_URL}/api/status", timeout=5)
        return r.json() if r.ok else {"ok": False}
    except Exception:
        return {"ok": False}


# —— 顶部标题 ——
st.title("📚 LangChain RAG 知识库")
st.caption("通义千问 + ChromaDB · 上传文档 → 提问")

status = get_status()

# 后端连不上
if not status.get("ok"):
    st.error("🔌 无法连接后端，请确认 FastAPI 已启动（端口 8000）")
    st.stop()

count = status.get("docs_count", 0)
key_ok = status.get("api_key_configured", False)

# Key 状态提示（不阻塞，只是提醒）
if not key_ok:
    st.warning(
        "⚠ **未配置 API Key**：服务已启动，界面可浏览，但上传/提问不可用。\n\n"
        "请编辑 `.env` 文件，填入 `DASHSCOPE_API_KEY`（[通义千问控制台申请]"
        "(https://bailian.console.aliyun.com/)），保存后重启后端。"
    )

st.sidebar.metric("向量库文档块数", count)
st.sidebar.metric("API Key", "✅ 已配置" if key_ok else "❌ 未配置")

# —— 上传区 ——
with st.sidebar.expander("📤 上传文档", expanded=True):
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
                st.error("无法连接后端，请确认 FastAPI 已启动（端口 8000）")
            except Exception as e:
                st.error(f"上传异常：{e}")

# —— 对话区 ——
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📎 引用来源（{len(msg['sources'])}）"):
                for i, s in enumerate(msg["sources"], 1):
                    st.caption(f"[{i}] {s['content']}")

# 输入框
if question := st.chat_input("基于知识库提问..."):
    if count == 0:
        st.warning("⚠ 向量库为空，请先在左侧上传文档。仍可提问但无 RAG 召回。")

    # 渲染用户消息
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # 流式回答
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                # 用流式接口，逐 chunk 拼接显示
                resp = requests.post(
                    f"{API_URL}/api/ask/stream",
                    json={"question": question, "k": 4},
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

                    # 记录到历史
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full, "sources": sources}
                    )
                    if sources:
                        with st.expander(f"📎 引用来源（{len(sources)}）"):
                            for i, s in enumerate(sources, 1):
                                st.caption(f"[{i}] {s['content']}")
            except requests.ConnectionError:
                st.error("无法连接后端，请确认 FastAPI 已启动（端口 8000）")
            except Exception as e:
                st.error(f"异常：{e}")
