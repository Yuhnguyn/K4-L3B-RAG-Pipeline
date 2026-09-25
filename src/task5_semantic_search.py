"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.

embed_texts và get_collection được import vào namespace của module này để
Task 5 dùng đúng model/dimension của Task 4 (và để test contract monkeypatch được).
"""

from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần."""
    if not query.strip() or top_k <= 0:
        return []

    query_vector = embed_texts([query])[0]
    response = get_collection().query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for item_id, content, metadata, distance in zip(
        response["ids"][0],
        response["documents"][0],
        response["metadatas"][0],
        response["distances"][0],
    ):
        results.append(
            {
                "id": item_id,
                "content": content,
                # Chroma cosine distance thuộc [0, 2]; đổi về similarity để sort giảm dần.
                # Kết quả có distance > 1 sẽ bị kẹp về 0 — vẫn hợp lệ, chỉ là hết phân biệt.
                "score": max(0.0, 1.0 - float(distance)),
                "metadata": dict(metadata),
                "retrieval_method": "dense",
            }
        )

    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for probe in ("Điều 4 quy định gì về tín chỉ", "sinh viên bị buộc thôi học khi nào"):
        print(f"\n=== {probe}")
        for result in semantic_search(probe, top_k=3):
            print(
                f"  {result['score']:.4f}  {result['id']}\n"
                f"          {' '.join(result['content'].split())[:110]}"
            )
