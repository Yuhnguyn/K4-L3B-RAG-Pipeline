"""
Task 8 — PageIndex vectorless fallback.

Lựa chọn của nhóm: KHÔNG gọi dịch vụ PageIndex từ xa, mà tự cài đặt một
vectorless retriever chạy cục bộ trên chính cây cấu trúc của corpus.

Lý do:
    1. PAGEINDEX_API_KEY chưa có, nên đường remote không chạy được và phần
       A/B trong báo cáo sẽ trống.
    2. Corpus là văn bản pháp quy đã được Task 3 khôi phục cây "# CHƯƠNG" /
       "## Điều". Đây đúng là loại dữ liệu mà vectorless navigation (đi theo
       mục lục thay vì embedding) phát huy tác dụng.

Cách hoạt động — hai tầng, không dùng embedding:
    Tầng 1: chấm điểm từng tài liệu bằng độ khớp giữa truy vấn với tiêu đề văn
            bản và toàn bộ tiêu đề Điều của nó -> chọn nhánh tài liệu.
    Tầng 2: trong các tài liệu đã chọn, chấm điểm từng node "Điều", ưu tiên
            khớp ở tiêu đề (trọng số 3) hơn khớp trong thân bài (trọng số 1).

Nếu sau này nhóm có API key, thay thân hàm pageindex_search() bằng lời gọi
PageIndexClient; phần còn lại của pipeline không phải sửa vì contract giữ nguyên.

Đây là dịch vụ fallback: Task 9 bọc try/except quanh pageindex_search() để lỗi
ở đây không làm pipeline dừng.
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from .task6_lexical_search import tokenize


load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
TREE_CACHE = Path(__file__).parent.parent / "chroma_db" / "pageindex_tree.json"

HEADING_PATTERN = re.compile(r"(?m)^(#{1,2})\s+(.+)$")
HEADING_WEIGHT = 3      # khớp ở tiêu đề Điều đáng giá hơn khớp trong thân bài
DOC_BRANCHES = 3        # số tài liệu giữ lại sau tầng 1

_tree: list[dict] | None = None
_idf: dict[str, float] | None = None


def _build_tree() -> list[dict]:
    """Dựng cây document -> node Điều từ Markdown đã chuẩn hóa."""
    from .task4_chunking_indexing import load_documents

    tree = []
    for document in load_documents():
        nodes = []
        matches = list(HEADING_PATTERN.finditer(document["content"]))
        for order, match in enumerate(matches):
            end = matches[order + 1].start() if order + 1 < len(matches) else len(document["content"])
            body = document["content"][match.end():end].strip()
            heading = match.group(2).strip()
            if not body:
                continue
            nodes.append({
                "node_id": f"{document['id']}::{match.group(1)}-{order}",
                "heading": heading,
                "body": body,
                "order": order,
            })

        if not nodes:
            # Bài viết news không có heading Chương/Điều: cả bài là một node.
            nodes = [{
                "node_id": f"{document['id']}::node-0",
                "heading": document["metadata"]["title"],
                "body": document["content"],
                "order": 0,
            }]

        tree.append({
            "doc_id": document["id"],
            "metadata": document["metadata"],
            "nodes": nodes,
        })
    return tree


def upload_documents() -> None:
    """Dựng và cache cây cấu trúc.

    Tương đương bước "upload + cache document ID" của PageIndex remote: chạy một
    lần, các lần search sau đọc lại cache thay vì dựng lại cây.
    """
    tree = _build_tree()
    TREE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TREE_CACHE.write_text(
        json.dumps(tree, ensure_ascii=False), encoding="utf-8"
    )
    nodes = sum(len(document["nodes"]) for document in tree)
    print(f"PageIndex tree: {len(tree)} documents, {nodes} nodes -> {TREE_CACHE.name}")


def _get_tree() -> list[dict]:
    """Đọc cây từ cache, dựng mới nếu chưa có."""
    global _tree
    if _tree is not None:
        return _tree

    if TREE_CACHE.exists():
        try:
            _tree = json.loads(TREE_CACHE.read_text(encoding="utf-8"))
            return _tree
        except (OSError, json.JSONDecodeError):
            pass   # cache hỏng thì dựng lại

    _tree = _build_tree()
    return _tree


def _get_idf() -> dict[str, float]:
    """IDF tính trên tập node.

    Cần thiết vì đếm token trần coi mọi từ ngang nhau: "sinh", "viên", "học"
    có mặt ở gần như mọi Điều nên không phân biệt được gì, trong khi "buộc",
    "phúc khảo" mới là từ định vị đúng Điều. Không có IDF thì truy vấn
    "sinh viên bị buộc thôi học" bị các Điều hành chính chung chung chiếm chỗ.
    """
    global _idf
    if _idf is not None:
        return _idf

    from collections import Counter
    from math import log

    document_freq: Counter[str] = Counter()
    total = 0
    for document in _get_tree():
        for node in document["nodes"]:
            total += 1
            document_freq.update(set(tokenize(f"{node['heading']} {node['body']}")))

    _idf = {
        token: log(total / (1 + freq)) + 1.0
        for token, freq in document_freq.items()
    }
    return _idf


def _weighted(query_tokens: set[str], tokens: set[str]) -> float:
    """Tổng IDF của các token truy vấn xuất hiện trong tokens."""
    idf = _get_idf()
    return sum(idf.get(token, 1.0) for token in query_tokens & tokens)


def _node_score(query_tokens: set[str], node: dict) -> float:
    """Điểm của một node: khớp tiêu đề nặng hơn, khớp thân bài có chuẩn hóa độ dài.

    Phần tiêu đề không chuẩn hóa vì các tiêu đề Điều dài tương đương nhau.
    Phần thân bài chia cho căn bậc hai số token riêng biệt, nếu không thì một
    bài news 3.000 ký tự sẽ đè bẹp đúng Điều cần tìm chỉ vì nó dài hơn.
    """
    heading_tokens = set(tokenize(node["heading"]))
    body_tokens = set(tokenize(node["body"]))
    return (
        _weighted(query_tokens, heading_tokens) * HEADING_WEIGHT
        + _weighted(query_tokens, body_tokens) / ((len(body_tokens) + 1) ** 0.5)
    )


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Trả về pageindex SearchResult."""
    if not query.strip() or top_k <= 0:
        return []

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return []

    tree = _get_tree()
    if not tree:
        return []

    # Tầng 1 — chọn nhánh tài liệu theo tiêu đề văn bản và tiêu đề các Điều.
    doc_scores = []
    for document in tree:
        # Dùng max thay vì tổng: một văn bản có nhiều Điều không vì thế mà
        # liên quan hơn, cái đáng kể là nó có Điều nào khớp mạnh nhất.
        best_heading = max(
            (_weighted(query_tokens, set(tokenize(node["heading"])))
             for node in document["nodes"]),
            default=0.0,
        )
        score = (
            _weighted(query_tokens, set(tokenize(document["metadata"]["title"])))
            * HEADING_WEIGHT
            + best_heading * HEADING_WEIGHT
        )
        doc_scores.append((score, document))
    doc_scores.sort(key=lambda pair: pair[0], reverse=True)

    branches = [document for score, document in doc_scores[:DOC_BRANCHES] if score > 0]
    if not branches:
        branches = [document for _, document in doc_scores]

    # Tầng 2 — chấm điểm từng node Điều trong các nhánh đã chọn.
    scored = []
    for document in branches:
        for node in document["nodes"]:
            score = _node_score(query_tokens, node)
            if score > 0:
                scored.append((score, document, node))

    if not scored:
        return []

    scored.sort(key=lambda triple: (-triple[0], triple[2]["order"]))
    best = scored[0][0]

    results = []
    for score, document, node in scored[:top_k]:
        results.append({
            "id": node["node_id"],
            "content": f"{node['heading']}\n{node['body']}",
            "score": score / best,   # chuẩn hóa về (0, 1], node tốt nhất = 1.0
            "metadata": {**document["metadata"], "chunk_index": node["order"]},
            "retrieval_method": "pageindex",
        })
    return results


if __name__ == "__main__":
    upload_documents()
    for probe in ("Sinh viên bị buộc thôi học khi nào", "Chuẩn ngoại ngữ đầu ra"):
        print(f"\n=== {probe}")
        for result in pageindex_search(probe, top_k=3):
            print(f"  {result['score']:.3f}  {result['id']}")
            print(f"          {' '.join(result['content'].split())[:100]}")
