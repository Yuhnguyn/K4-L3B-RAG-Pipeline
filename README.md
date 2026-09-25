# Day 8 — RAG Pipeline: Hỏi đáp quy chế UIT

Chatbot RAG trả lời câu hỏi về **quy chế và quy định đào tạo của Trường Đại học
Công nghệ Thông tin (UIT), ĐHQG-HCM**, có hybrid retrieval, citation kiểm chứng
được, giao diện chat và báo cáo đánh giá A/B.

## Chủ đề và dữ liệu

- **6 văn bản pháp quy** (PDF text Unicode) trong `data/landing/legal/`: quy chế
  đào tạo tín chỉ, tổ chức thi tập trung, đào tạo ngoại ngữ, khóa luận tốt
  nghiệp, chương trình tài năng, dạy học trực tuyến.
- **7 bài viết/thông báo công khai** trong `data/landing/news/`, crawl bằng
  Crawl4AI.
- Chuẩn hóa sang Markdown có YAML frontmatter, khôi phục cây `# CHƯƠNG` /
  `## Điều`, rồi chunk **hai tầng** (heading → ký tự) thành **396 đoạn** trong
  ChromaDB.

## Pipeline

```
convert → chunk → index → dense + BM25 → RRF → fallback → generation có citation
```

| Tầng | File | Ghi chú |
| --- | --- | --- |
| Thu thập | `src/task1_collect_legal_docs.py`, `src/task2_crawl_news.py` | nguồn công khai, có URL đối chiếu |
| Chuẩn hóa | `src/task3_convert_markdown.py` | nối dòng PDF, khôi phục heading, frontmatter |
| Chunk + index | `src/task4_chunking_indexing.py` | `bge-m3` (1024 chiều), ChromaDB cosine, dọn chunk mồ côi, mở rộng viết tắt |
| Dense | `src/task5_semantic_search.py` | cùng `embed_texts()` với Task 4 |
| BM25 | `src/task6_lexical_search.py` | BM25Plus, tokenizer giữ mã văn bản |
| Fusion | `src/task7_reranking.py` | RRF `k=60`, rank từ 1, fuse một lần |
| Fallback | `src/task8_pageindex_vectorless.py` | vectorless cục bộ, duyệt cây Chương/Điều |
| Pipeline | `src/task9_retrieval_pipeline.py` | ngưỡng fallback theo cosine gốc (0.55) |
| Generation | `src/task10_generation.py` | reorder, citation, safe refusal |
| Hội thoại | `src/conversation_memory.py` | viết lại câu hỏi nối tiếp thành câu hỏi độc lập |
| Viết tắt | `src/glossary.py` | chèn dạng đầy đủ của KLTN/CBPB... vào chunk lúc index |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

Điền API key cần dùng trong `.env`; không commit file này.

```bash
# 1. Thu thập và chuẩn hoá
python -m src.task1_collect_legal_docs
python -m src.task2_crawl_news
python -m src.task3_convert_markdown

# 2. Chunk, embedding, index (tải bge-m3 lần đầu, ~2GB)
python -m src.task4_chunking_indexing

# 3. Kiểm tra contract
pytest -q

# 4. Chạy sản phẩm
streamlit run app.py
```

> Lưu ý vận hành: không chạy `app.py` cùng lúc với `task4_chunking_indexing`.
> ChromaDB `PersistentClient` không an toàn khi hai tiến trình cùng mở một thư
> mục và có thể làm hỏng file HNSW index.

## Đánh giá

```bash
python -m src.run_evaluation   # chạy A/B rồi ghi raw_results.json
```

- **Config A — dense-only:** `retrieve(..., use_reranking=False)`.
- **Config B — hybrid + RRF:** `retrieve(..., use_reranking=True)`.
- Golden dataset 15 câu (5 keyword / 5 semantic / 5 confusable), 4 metric RAGAS.

Kết quả: Config A average **0.8178**, Config B **0.7961** — trên corpus này RRF
không cải thiện. Phân tích đầy đủ, gồm cả một thí nghiệm prompt bị bác bỏ bằng số
đo, ở [`group_project/evaluation/RESULT.md`](group_project/evaluation/RESULT.md).

### Dùng endpoint LLM khác (ví dụ Command Code)

`call_llm` và evaluator tôn trọng `OPENAI_BASE_URL`, nên trỏ được sang bất kỳ
endpoint OpenAI-compatible:

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=deepseek/deepseek-v4.1-flash
OPENAI_API_KEY=<key>
OPENAI_BASE_URL=https://api.commandcode.ai/provider/v1
# Endpoint này không có embeddings -> RAGAS chấm bằng bge-m3 cục bộ:
EVALUATOR_EMBEDDING_PROVIDER=sentence_transformers
```

Khi đổi LLM/evaluator, phải chạy lại **cả** baseline lẫn candidate bằng cùng một
cấu hình; nếu không, delta metric sẽ lẫn giữa thay đổi retrieval và thay đổi giám khảo.

### Đo A/B mở rộng viết tắt (Recommendation #1)

```bash
# Baseline — tắt mở rộng viết tắt
GLOSSARY_EXPANSION=0 python -m src.task4_chunking_indexing
GLOSSARY_EXPANSION=0 python -m src.run_evaluation
cp group_project/evaluation/raw_results.json raw_results_baseline.json

# Candidate — bật mở rộng viết tắt
GLOSSARY_EXPANSION=1 python -m src.task4_chunking_indexing
GLOSSARY_EXPANSION=1 python -m src.run_evaluation

python -m src.compare_evaluation \
    raw_results_baseline.json group_project/evaluation/raw_results.json
```

## Kiểm tra

```bash
pytest tests/test_contracts.py -q      # schema, interface, invariant
pytest tests/test_acceptance.py -q     # dữ liệu, golden dataset, báo cáo
pytest -q                              # toàn bộ
```

## Tài liệu

- [Module contracts](docs/MODULE_CONTRACTS.md): schema, interface, invariant.
- [Step-by-step guide](docs/STEP_BY_STEP.md): thứ tự triển khai.
- [Grading rubric](docs/GRADING_RUBRIC.md): thang điểm.
- [Individual report template](reports/INDIVIDUAL_REPORT.md): báo cáo cá nhân.
- [Suggested topics](docs/SUGGESTED_TOPICS.md): danh sách chủ đề tham khảo.
