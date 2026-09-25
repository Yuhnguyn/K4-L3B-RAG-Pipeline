"""
Task 7 — Reciprocal Rank Fusion.

RRF gộp nhiều bảng xếp hạng mà không cộng trực tiếp cosine score với BM25
score. Công thức: RRF(d) = sum(1 / (k + rank)), rank bắt đầu từ 1.

Lưu ý: RRF score chỉ phản ánh thứ hạng, không dùng để quyết định fallback.

Vì sao phải copy item trước khi thay score: Task 9 đọc cosine score gốc từ
danh sách dense để quyết định fallback. Nếu RRF ghi đè score trực tiếp lên item
của danh sách đầu vào thì cosine score (~0.6) bị thay bằng RRF score (~0.03),
và mọi truy vấn sẽ rơi xuống dưới threshold.
"""


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse nhiều ranked lists và trả hybrid SearchResult."""
    if top_k <= 0:
        return []

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):   # rank bắt đầu từ 1
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            # Giữ bản gặp đầu tiên: mọi danh sách đều mang cùng content/metadata
            # cho một ID, chỉ khác score và retrieval_method.
            items.setdefault(item_id, item)

    ranked_ids = sorted(scores, key=lambda item_id: scores[item_id], reverse=True)

    results = []
    for item_id in ranked_ids[:top_k]:
        result = items[item_id].copy()   # không sửa item của danh sách đầu vào
        result["score"] = scores[item_id]
        result["retrieval_method"] = "hybrid"
        results.append(result)
    return results


if __name__ == "__main__":
    dense = [
        {"id": "chunk-0", "content": "a", "score": 0.9, "metadata": {}, "retrieval_method": "dense"},
        {"id": "chunk-1", "content": "b", "score": 0.8, "metadata": {}, "retrieval_method": "dense"},
    ]
    bm25 = [
        {"id": "chunk-1", "content": "b", "score": 7.0, "metadata": {}, "retrieval_method": "bm25"},
        {"id": "chunk-2", "content": "c", "score": 5.0, "metadata": {}, "retrieval_method": "bm25"},
    ]
    print("dense:", [(x["id"], x["score"]) for x in dense])
    print("bm25 :", [(x["id"], x["score"]) for x in bm25])
    print("fused:")
    for item in rerank_rrf([dense, bm25], top_k=3):
        print(f"  {item['score']:.5f}  {item['id']}  {item['retrieval_method']}")
    print("dense sau khi fuse (phải giữ nguyên):",
          [(x["id"], x["score"]) for x in dense])
