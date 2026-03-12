from __future__ import annotations

from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from infra.embeddings import E5InstructEmbeddings, E5_MODEL_NAME


DATA_DIR = Path("data")
CACHE_DIR = Path(".cache/vectorstore")
EMBEDDING_META_FILE = "embedding_model.txt"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
RETRIEVE_K = 5

# 모듈 수준 캐시: 같은 프로세스 내에서 반복 로딩 방지
_vectorstore_cache: dict[str, FAISS] = {}


def _get_embeddings() -> E5InstructEmbeddings:
    return E5InstructEmbeddings()


def _meta_path(cache_dir: Path) -> Path:
    return cache_dir / EMBEDDING_META_FILE


def _write_embedding_meta(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _meta_path(cache_dir).write_text(E5_MODEL_NAME, encoding="utf-8")


def _embedding_meta_matches(cache_dir: Path) -> bool:
    meta_file = _meta_path(cache_dir)
    if not meta_file.exists():
        return False
    cached_model = meta_file.read_text(encoding="utf-8").strip()
    return cached_model == E5_MODEL_NAME


def _should_rebuild(data_dir: Path, cache_dir: Path) -> bool:
    """캐시가 없거나 PDF보다 오래됐으면 재빌드 필요."""
    index_path = cache_dir / "index.faiss"
    if not index_path.exists():
        return True
    if not _embedding_meta_matches(cache_dir):
        return True
    cache_mtime = index_path.stat().st_mtime
    for pdf in data_dir.glob("**/*.pdf"):
        if pdf.stat().st_mtime > cache_mtime:
            return True
    return False


def _build_from_pdfs(data_dir: Path, embeddings: E5InstructEmbeddings) -> Optional[FAISS]:
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
    """data/ 하위 PDF 전체를 대상으로 FAISS 인덱스를 빌드/로드한다."""
    cache_key = str(cache_dir.resolve())
    if cache_key in _vectorstore_cache:
        return _vectorstore_cache[cache_key]

    if not data_dir.exists() or not any(data_dir.glob("**/*.pdf")):
        return None

    embeddings = _get_embeddings()

    if not _should_rebuild(data_dir, cache_dir):
        try:
            vectorstore = FAISS.load_local(
                str(cache_dir),
                embeddings,
                allow_dangerous_deserialization=True,
            )
        except Exception:
            vectorstore = _build_from_pdfs(data_dir, embeddings)
            if vectorstore is not None:
                cache_dir.mkdir(parents=True, exist_ok=True)
                vectorstore.save_local(str(cache_dir))
                _write_embedding_meta(cache_dir)
    else:
        vectorstore = _build_from_pdfs(data_dir, embeddings)
        if vectorstore is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            vectorstore.save_local(str(cache_dir))
            _write_embedding_meta(cache_dir)

    if vectorstore is not None:
        _vectorstore_cache[cache_key] = vectorstore

    return vectorstore


def retrieve_relevant_context(vectorstore: FAISS, query: str, k: int = RETRIEVE_K) -> str:
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


def retrieve_market_context(vectorstore: FAISS, query: str, k: int = RETRIEVE_K) -> str:
    return retrieve_relevant_context(vectorstore, query, k=k)
