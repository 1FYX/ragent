"""
文档加载与切片：用 LangChain 标准组件，不手写。

- 加载：按文件类型分发（PDF / TXT / MD / DOCX）
- 切片：RecursiveCharacterTextSplitter（递归切分，保持语义）
"""
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
    UnstructuredWordDocumentLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 按 chunk_size / overlap 切分。这俩值是 RAG 经验值，简历可讲。
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def load_file(file_path: str) -> list[Document]:
    """根据扩展名加载文件为 Document 列表。"""
    p = Path(file_path)
    ext = p.suffix.lower()

    loader_map = {
        ".pdf": PyPDFLoader,
        ".txt": TextLoader,
        ".md": UnstructuredMarkdownLoader,
        ".docx": UnstructuredWordDocumentLoader,
    }

    loader_cls = loader_map.get(ext)
    if not loader_cls:
        raise ValueError(f"不支持的文件类型：{ext}（支持 PDF/TXT/MD/DOCX）")

    # TextLoader 默认单行编码，显式指定 utf-8 避免中文乱码
    if loader_cls is TextLoader:
        return loader_cls(file_path, encoding="utf-8").load()
    return loader_cls(file_path).load()


def split_documents(
    docs: list[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    """递归切分文档。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # 分隔符优先级：段落 → 换行 → 句号 → 空格（中英文都照顾）
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    )
    return splitter.split_documents(docs)


def load_and_split(file_path: str) -> list[Document]:
    """一步到位：加载 + 切片。返回切好的块。"""
    docs = load_file(file_path)
    return split_documents(docs)
