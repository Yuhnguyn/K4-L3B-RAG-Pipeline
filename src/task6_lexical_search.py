"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.

CORPUS được nạp từ chính ChromaDB của Task 4 chứ không chunk lại: chunk lại là
hai corpus khác nhau, ID sẽ lệch và fusion ở Task 7 không ghép được.
"""

import re

from .task4_chunking_indexing import get_collection


CORPUS: list[dict] = []

# Giữ chữ (kể cả tiếng Việt có dấu), số, và các token ghép bằng "/" hoặc "-"
# để "790/QĐ-ĐHCNTT" hay "Anh-Việt" không bị vỡ vụn.
TOKEN_PATTERN = re.compile(r"[0-9a-zÀ-ỹ]+(?:[/-][0-9a-zÀ-ỹ]+)*")

_bm25_cache: tuple[int, object] | None = None


def tokenize(text: str) -> list[str]:
    """Tách token. Token ghép được giữ nguyên và tách thêm thành phần con."""
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(text.lower()):
        tokens.append(token)
        if "/" in token or "-" in token:
            # "790/qđ-đhcntt" khớp được cả khi người dùng chỉ gõ "790" hoặc "đhcntt".
            tokens.extend(part for part in re.split(r"[/-]", token) if part)
    return tokens


def load_corpus() -> list[dict]:
    """Đọc lại đúng những chunk Task 4 đã index."""
    collection = get_collection()
    response = collection.get(include=["documents", "metadatas"])
    return [
        {"id": item_id, "content": content, "metadata": dict(metadata)}
        for item_id, content, metadata in zip(
            response["ids"], response["documents"], response["metadatas"]
        )
    ]


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4.

    Dùng BM25Plus thay vì BM25Okapi. Công thức Okapi tính
    idf = log(N - n + 0.5) - log(n + 0.5), nên với term xuất hiện ở đúng một nửa
    số tài liệu thì idf = 0 và mọi score về 0 — corpus càng nhỏ càng dễ suy biến.
    BM25Plus (Lv & Zhai, 2011) thêm cận dưới delta nên xếp hạng vẫn đúng.
    Đánh đổi: không còn ngưỡng 0 tự nhiên để lọc "không khớp gì", nhưng Task 9
    dùng dense score làm ngưỡng fallback nên không ảnh hưởng.
    """
    from rank_bm25 import BM25Plus

    return BM25Plus([tokenize(item["content"]) for item in corpus])


def _get_corpus_and_index() -> tuple[list[dict], object]:
    """Lấy corpus hiện hành và BM25 index tương ứng, cache theo identity của list."""
    global CORPUS, _bm25_cache

    corpus = CORPUS
    if not corpus:
        corpus = CORPUS = load_corpus()

    if _bm25_cache is None or _bm25_cache[0] != id(corpus):
        _bm25_cache = (id(corpus), build_bm25_index(corpus))
    return corpus, _bm25_cache[1]


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    if not query.strip() or top_k <= 0:
        return []

    corpus, bm25 = _get_corpus_and_index()
    if not corpus:
        return []

    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(corpus)), key=lambda i: scores[i], reverse=True)

    results = []
    for index in ranked[:top_k]:
        if scores[index] <= 0:
            continue
        item = corpus[index]
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": float(scores[index]),
                "metadata": dict(item["metadata"]),
                "retrieval_method": "bm25",
            }
        )
    return results


if __name__ == "__main__":
    for probe in ("Điều 4 quy định gì về tín chỉ", "sinh viên bị buộc thôi học khi nào"):
        print(f"\n=== {probe}")
        for result in lexical_search(probe, top_k=3):
            print(
                f"  {result['score']:.4f}  {result['id']}\n"
                f"          {' '.join(result['content'].split())[:110]}"
            )
