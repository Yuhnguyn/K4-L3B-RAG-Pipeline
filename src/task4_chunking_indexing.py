"""
Task 4 — Chunking, embedding và indexing.

Luồng: data/standardized/*.md -> Document -> Chunk -> embedding -> ChromaDB.
Mọi Document/Chunk theo docs/MODULE_CONTRACTS.md. Task 5 dùng chung embed_texts()
để query vector và corpus vector cùng model, cùng số chiều.

Quyết định thiết kế (giải thích đầy đủ trong group_project/evaluation/RESULT.md):
    - CHUNK_SIZE 800 thay vì 500: trung vị một "Điều" trong corpus là 799 ký tự.
    - Chunk hai tầng: tách theo heading Chương/Điều trước, cắt theo ký tự sau.
    - Mỗi chunk con mang theo tên Điều của nó để không mất ngữ cảnh.
    - Sau upsert phải dọn chunk mồ côi, vì upsert không tự xóa ID cũ.
"""

import os
import re
from pathlib import Path

import yaml

from .contracts import validate_document
from .glossary import expand_for_indexing


STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Giải thích lựa chọn tham số trong báo cáo nhóm.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
CHUNKING_METHOD = "markdown_header + recursive"

# Section ngắn hơn ngưỡng này (ví dụ dòng "# CHƯƠNG I / NHỮNG QUY ĐỊNH CHUNG")
# không đủ nội dung để thành một chunk; nó được gộp làm ngữ cảnh cho section kế tiếp.
MIN_SECTION_CHARS = 50

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = 1024

COLLECTION_NAME = "rag_documents"

FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n+", re.S)

_model = None


def _get_model():
    """Cache model ở module level: load lại mỗi lần gọi sẽ rất chậm ở Task 5."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed danh sách text. Task 4 dùng cho corpus, Task 5 dùng cho query."""
    if not texts:
        return []
    provider = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers")
    if provider != "sentence_transformers":
        raise NotImplementedError(f"EMBEDDING_PROVIDER={provider} chưa được hỗ trợ")

    vectors = _get_model().encode(
        texts,
        batch_size=8,
        normalize_embeddings=True,   # cosine space của Chroma
        show_progress_bar=len(texts) > 32,
    )
    return [vector.tolist() for vector in vectors]


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _parse_frontmatter(raw: str, fallback_source: str, doc_type: str) -> tuple[dict, str]:
    """Tách YAML frontmatter khỏi thân bài; frontmatter không được đưa vào embedding."""
    match = FRONTMATTER_PATTERN.match(raw)
    if not match:
        return (
            {
                "source": fallback_source,
                "title": Path(fallback_source).stem,
                "doc_type": doc_type,
                "url": None,
            },
            raw.strip(),
        )

    parsed = yaml.safe_load(match.group(1)) or {}
    metadata = {
        "source": str(parsed.get("source") or fallback_source),
        "title": str(parsed.get("title") or Path(fallback_source).stem),
        "doc_type": str(parsed.get("doc_type") or doc_type),
        "url": str(parsed["url"]) if parsed.get("url") else None,
    }
    return metadata, raw[match.end():].strip()


def load_documents() -> list[dict]:
    """Đọc Markdown trong standardized/ và trả về danh sách Document."""
    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        doc_type = "legal" if "legal" in path.parts else "news"
        metadata, body = _parse_frontmatter(
            path.read_text(encoding="utf-8"), path.name, doc_type
        )
        if not body:
            continue

        document = {
            "id": path.relative_to(STANDARDIZED_DIR).as_posix(),
            "content": body,
            "metadata": metadata,
        }
        validate_document(document)
        documents.append(document)
    return documents


def _split_by_heading(content: str) -> list[tuple[str, str]]:
    """Tách theo heading Chương/Điều -> [(tiêu đề ngữ cảnh, nội dung)]."""
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "chuong"), ("##", "dieu")],
        strip_headers=False,
    )
    sections = splitter.split_text(content)
    if not sections:
        return [("", content)]

    output = []
    for section in sections:
        heading = section.metadata.get("dieu") or section.metadata.get("chuong") or ""
        output.append((heading.strip(), section.page_content))
    return output


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id ổn định và chunk_index liên tục."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    chunks: list[dict] = []
    for document in documents:
        index = 0
        carried = ""   # tiêu đề Chương hoặc section quá ngắn, chờ gộp vào section sau
        for heading, section in _split_by_heading(document["content"]):
            body = section.strip()
            if len(body) < MIN_SECTION_CHARS:
                # Không đủ nội dung để đứng riêng: giữ lại làm ngữ cảnh cho section kế tiếp
                # thay vì tạo ra một chunk chỉ chứa dòng tiêu đề.
                carried = f"{carried}{body}\n" if body else carried
                continue

            # Chunk con thứ 2 trở đi không còn dòng "Điều N", nên phải gắn lại tiêu đề —
            # nếu không thì cả dense lẫn BM25 đều không biết nó thuộc Điều nào.
            prefix = f"{heading}\n" if heading else ""
            section = f"{carried}{body}" if carried else body
            carried = ""
            budget = max(CHUNK_SIZE - len(prefix), 200)

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=budget,
                chunk_overlap=min(CHUNK_OVERLAP, budget // 4),
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            for position, text in enumerate(splitter.split_text(section)):
                body = text.strip()
                if not body:
                    continue
                content = f"{prefix}{body}" if position else body
                # Chèn dạng đầy đủ của viết tắt có trong chunk (Recommendation #1
                # trong RESULT.md). Phần thân giữ nguyên văn; chú thích nằm ở cuối.
                content = expand_for_indexing(content)
                chunks.append(
                    {
                        "id": f"{document['id']}::chunk-{index}",
                        "content": content,
                        "metadata": {**document["metadata"], "chunk_index": index},
                    }
                )
                index += 1
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk, giữ nguyên các field khác."""
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    return chunks


def _to_chroma_metadata(metadata: dict) -> dict:
    """Chroma không nhận giá trị None trong metadata; contract lại cho phép url=None."""
    return {key: ("" if value is None else value) for key, value in metadata.items()}


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks và dọn chunk mồ côi của những document vừa được index lại."""
    if not chunks:
        return

    collection = get_collection()
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[_to_chroma_metadata(chunk["metadata"]) for chunk in chunks],
    )

    # upsert chỉ ghi đè ID trùng. Khi CHUNK_SIZE đổi, số chunk giảm và những ID cũ
    # có chunk_index cao vẫn nằm lại -> thành rác và vẫn bị search trả về.
    current_ids = set(collection.get(include=[])["ids"])
    fresh_ids = {chunk["id"] for chunk in chunks}
    touched_docs = {chunk["id"].split("::")[0] for chunk in chunks}
    orphans = [
        item_id
        for item_id in current_ids - fresh_ids
        if item_id.split("::")[0] in touched_docs
    ]
    if orphans:
        collection.delete(ids=orphans)
        print(f"Đã xóa {len(orphans)} chunk mồ côi từ lần index trước")


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    print(
        f"{len(documents)} documents -> {len(chunks)} chunks "
        f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})"
    )

    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
