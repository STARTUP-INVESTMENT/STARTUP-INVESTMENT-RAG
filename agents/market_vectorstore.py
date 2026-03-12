from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .startup_search_agent import load_env_file


DATA_DIR = Path("data")
CACHE_DIR = Path(".cache/market_vectorstore")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
RETRIEVE_K = 5

# 모듈 수준 캐시: 같은 프로세스 내에서 반복 로딩 방지
_vectorstore_cache: dict[str, FAISS] = {}


def _get_embeddings() -> OpenAIEmbeddings:
    load_env_file(Path.cwd() / ".env")
    return OpenAIEmbeddings(api_key=os.environ.get("OPENAI_API_KEY", ""))


def _should_rebuild(data_dir: Path, cache_dir: Path) -> bool:
    """캐시가 없거나 PDF보다 오래됐으면 재빌드 필요."""
    index_path = cache_dir / "index.faiss"
    if not index_path.exists():
        return True
    cache_mtime = index_path.stat().st_mtime
    for pdf in data_dir.glob("**/*.pdf"):
        if pdf.stat().st_mtime > cache_mtime:
            return True
    return False


def _build_from_pdfs(data_dir: Path, embeddings: OpenAIEmbeddings) -> Optional[FAISS]:
    pdf_files = list(data_dir.glob("**/*.pdf"))
    if not pdf_files:
        return None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    all_docs = []
    for pdf_path in pdf_files:
        try:
            docs = PyPDFLoader(str(pdf_path)).load_and_split(splitter)
            all_docs.extend(docs)
        except Exception:
            continue

    if not all_docs:
        return None

    return FAISS.from_documents(all_docs, embeddings)


def load_or_build_vectorstore(
    data_dir: Path = DATA_DIR,
    cache_dir: Path = CACHE_DIR,
) -> Optional[FAISS]:
    """
    data_dir 에 PDF가 있으면 FAISS 인덱스를 빌드/로드해 반환한다.
    PDF가 없으면 None을 반환한다(market_evaluation은 도메인 컨텍스트만 사용).
    같은 프로세스 내에서는 모듈 캐시로 중복 로딩을 막는다.
    """
    cache_key = str(cache_dir.resolve())
    if cache_key in _vectorstore_cache:
        return _vectorstore_cache[cache_key]

    if not data_dir.exists() or not any(data_dir.glob("**/*.pdf")):
        return None

    embeddings = _get_embeddings()

    if not _should_rebuild(data_dir, cache_dir):
        vectorstore = FAISS.load_local(
            str(cache_dir),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    else:
        vectorstore = _build_from_pdfs(data_dir, embeddings)
        if vectorstore is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            vectorstore.save_local(str(cache_dir))

    if vectorstore is not None:
        _vectorstore_cache[cache_key] = vectorstore

    return vectorstore


def retrieve_market_context(vectorstore: FAISS, query: str, k: int = RETRIEVE_K) -> str:
    """유사도 검색으로 관련 청크를 합쳐 하나의 컨텍스트 문자열로 반환한다."""
    docs = vectorstore.similarity_search(query, k=k)
    if not docs:
        return ""
    chunks = []
    for doc in docs:
        source = Path(doc.metadata.get("source", "")).name
        page = doc.metadata.get("page", "")
        header = f"[{source} p.{page}]" if source else "[market doc]"
        chunks.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(chunks)
