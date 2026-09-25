"""
Task 9 — Retrieval pipeline hoàn chỉnh.

Luồng xử lý:
    1. Chạy semantic_search và lexical_search.
    2. Fuse hai danh sách bằng RRF đúng một lần.
    3. Lấy best cosine score gốc từ dense results.
    4. Nếu score dưới threshold, thử PageIndex fallback.
    5. Nếu fallback lỗi, trả hybrid results thay vì crash.

Không so sánh threshold với RRF score vì hai thang đo khác nhau.
RRF score luôn rất nhỏ (~0.03) nên nếu lỡ dùng nó làm ngưỡng thì mọi truy vấn
đều rơi xuống dưới và fallback kích hoạt vô điều kiện.

SCORE_THRESHOLD = 0.55 được hiệu chỉnh trên corpus này bằng 6 truy vấn trong
chủ đề (best dense 0.6282–0.7391) và 5 truy vấn ngoài chủ đề (0.3432–0.4361).
Chi tiết trong group_project/evaluation/RESULT.md. Giá trị này không đúng cho
corpus, model embedding hay cách chunk khác — phải đo lại khi thay đổi.
"""

import os

from dotenv import load_dotenv

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


load_dotenv()

SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD") or 0.55)
DEFAULT_TOP_K = 5

# Lấy rộng hơn top_k ở mỗi nhánh để RRF có đủ ứng viên chồng lấn giữa hai danh sách.
CANDIDATE_MULTIPLIER = 2


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Trả về hybrid hoặc pageindex SearchResult."""
    if not query.strip() or top_k <= 0:
        return []

    candidates = top_k * CANDIDATE_MULTIPLIER
    dense = semantic_search(query, top_k=candidates)
    sparse = lexical_search(query, top_k=candidates)

    # Đọc cosine score gốc TRƯỚC khi fuse. rerank_rrf() đã copy item nên không
    # sửa danh sách đầu vào, nhưng đọc trước là lớp phòng vệ thứ hai.
    best_dense_score = dense[0]["score"] if dense else 0.0

    # Fuse đúng một lần, kể cả khi dense tự tin — nhánh quyết định fallback nằm
    # ở dưới và dùng score khác, không phải kết quả của RRF.
    hybrid = (
        rerank_rrf([dense, sparse], top_k=top_k)
        if use_reranking
        else dense[:top_k]
    )

    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query, top_k=top_k)
        except Exception as error:
            # Fallback là dịch vụ phụ: hỏng thì pipeline vẫn phải trả kết quả.
            print(f"PageIndex fallback lỗi ({type(error).__name__}: {error}) — dùng hybrid")
        else:
            if fallback:
                return fallback[:top_k]

    return hybrid[:top_k]


if __name__ == "__main__":
    probes = [
        ("trong chủ đề", "Sinh viên bị buộc thôi học trong trường hợp nào?"),
        ("trong chủ đề", "Một tín chỉ học tập bằng bao nhiêu tiết lý thuyết?"),
        ("ngoài chủ đề", "Cách nấu phở bò ngon tại nhà"),
    ]
    print(f"SCORE_THRESHOLD = {SCORE_THRESHOLD}\n")
    for label, probe in probes:
        results = retrieve(probe, top_k=3)
        method = results[0]["retrieval_method"] if results else "none"
        print(f"=== [{label}] {probe}")
        print(f"    -> {method}, {len(results)} kết quả")
        for item in results:
            print(f"    {item['score']:.4f}  {item['id']}")
            print(f"            {' '.join(item['content'].split())[:95]}")
        print()
