"""
RAG 核心链：用 LangChain LCEL 编排"检索 → 拼 prompt → 生成"。

设计：
- Embedding / LLM 走通义千问（OpenAI 兼容模式）
- 向量库用 ChromaDB（本地持久化，开发期零配置）
- 整条链用 LCEL（LangChain Expression Language）组合，可流式输出
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from openai import OpenAI

load_dotenv()

# —— 配置（从 .env 读） ——
BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen-plus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"))


def is_api_key_configured() -> bool:
    """是否已配置有效 API Key（供 UI/接口显示状态用，不抛错）。"""
    return bool(API_KEY) and not API_KEY.startswith("sk-xxxxxxxx")


def _check_api_key() -> None:
    """真正调用通义前检查；未配置则抛错（被上层捕获转成友好提示）。"""
    if not is_api_key_configured():
        raise RuntimeError(
            "未配置 DASHSCOPE_API_KEY。请复制 .env.example 为 .env，"
            "填入通义千问的 API Key（https://bailian.console.aliyun.com/ 申请）。"
        )


class DashscopeEmbeddings(Embeddings):
    """
    自定义 Embeddings：直接用原生 openai SDK 调通义。

    为什么不用 langchain_openai.OpenAIEmbeddings？
    因为 langchain-openai 1.4.x 改了 embedding 请求格式（传 contents 而非 input），
    通义千问只认标准 OpenAI 格式，会报 "contents is neither str nor list of str"。
    这里直接走原生 SDK，彻底绕开该 bug。
    """

    def __init__(self, model: str, base_url: str, api_key: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # 文档入库用：批量
        resp = self._client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimensions
        )
        return [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]

    def embed_query(self, text: str) -> list[float]:
        # 查询用：单条
        resp = self._client.embeddings.create(
            model=self.model, input=text, dimensions=self.dimensions
        )
        return resp.data[0].embedding


def get_embeddings() -> DashscopeEmbeddings:
    """通义 embedding（原生 SDK 直连，OpenAI 兼容模式）。"""
    _check_api_key()
    return DashscopeEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=BASE_URL,
        api_key=API_KEY,
        dimensions=EMBEDDING_DIM,
    )


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """通义 chat 模型（OpenAI 兼容）。"""
    _check_api_key()
    return ChatOpenAI(
        model=CHAT_MODEL,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=temperature,
    )


# —— Prompt：RAG 经典模板 ——
RAG_PROMPT = ChatPromptTemplate.from_template(
    """你是一个严谨的知识库问答助手。请优先依据下面的「参考资料」回答用户问题；
若资料不足，可结合自身知识但需说明。回答要准确、简洁。

参考资料：
{context}

用户问题：{question}

回答："""
)


def _format_docs(docs: list[Document]) -> str:
    """把检索到的文档拼成纯文本上下文。"""
    if not docs:
        return "（无相关资料）"
    return "\n\n".join(
        f"[{i + 1}] {doc.page_content}" for i, doc in enumerate(docs)
    )


class RAGChain:
    """封装 RAG 链：负责建库、检索、问答。"""

    def __init__(self, collection_name: str = "default"):
        self.collection_name = collection_name
        PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self._embeddings = get_embeddings()
        self._vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self._embeddings,
            persist_directory=str(PERSIST_DIR),
        )

    # —— 写入：批量入向量库 ——
    def add_documents(self, docs: list[Document]) -> int:
        """把切好的文档块写入向量库，返回写入数量。"""
        if not docs:
            return 0
        ids = [f"{self.collection_name}-{i}" for i in range(len(docs))]
        self._vectorstore.add_documents(docs, ids=ids)
        return len(docs)

    # —— 检索：top-k 相关文档 ——
    def as_retriever(self, k: int = 4):
        return self._vectorstore.as_retriever(search_kwargs={"k": k})

    # —— 问答：非流式 ——
    def ask(self, question: str, k: int = 4) -> tuple[str, list[Document]]:
        """问一个问题，返回 (答案, 引用来源)。"""
        retriever = self.as_retriever(k)
        chain = (
            {"context": retriever | _format_docs, "question": RunnablePassthrough()}
            | RAG_PROMPT
            | get_llm()
            | StrOutputParser()
        )
        answer = chain.invoke(question)
        sources = retriever.invoke(question)
        return answer, sources

    # —— 问答：流式 ——
    def ask_stream(self, question: str, k: int = 4):
        """流式问答，逐 token yield。"""
        retriever = self.as_retriever(k)
        chain = (
            {"context": retriever | _format_docs, "question": RunnablePassthrough()}
            | RAG_PROMPT
            | get_llm()
            | StrOutputParser()
        )
        # 先单独取一次引用来源（流式链不返回中间结果）
        sources = retriever.invoke(question)
        yield sources
        for chunk in chain.stream(question):
            yield chunk
