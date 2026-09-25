# Individual contribution report

> **Bản nháp.** Đổi tên file thành `reports/<student-id>-<short-name>.md`, điền phần
> Thông tin, và **rà lại cột "Việc tôi trực tiếp làm"** — chỉ giữ những dòng đúng là
> phần việc của bạn, xóa phần do thành viên khác phụ trách. Phần cuối là lời xác nhận
> có chữ ký nên nội dung phải phản ánh đúng thực tế.

---

## Thông tin

- Họ và tên:
- Mã học viên:
- Nhóm:
- Repository/branch: `K4-L3A-RAG-Pipeline`, commit `6a2a2d4`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Thu thập corpus | Chọn chủ đề quy chế UIT, xác minh `robots.txt`, sàng 69 PDF để lọc ra 6 file có text Unicode thật | `src/task1_collect_legal_docs.py`, `data/landing/legal/` | Done |
| Crawl bài viết | Viết `crawl_article()` với cấu hình theo domain (React SPA vs Drupal), lọc boilerplate và link spam | `src/task2_crawl_news.py`, `data/landing/news/` | Done |
| Chuẩn hóa Markdown | Nối dòng bị PDF cắt, khôi phục heading Chương/Điều, nhúng YAML frontmatter | `src/task3_convert_markdown.py`, `data/standardized/` | Done |
| Chunking + indexing | Chunk hai tầng 800/120, dọn chunk mồ côi sau upsert | `src/task4_chunking_indexing.py` | Done |
| Dense + BM25 | `semantic_search()`, `lexical_search()` với tokenizer giữ mã văn bản | `src/task5_semantic_search.py`, `src/task6_lexical_search.py` | Done |
| RRF + fallback | `rerank_rrf()`, vectorless retriever cục bộ, pipeline `retrieve()` có ngưỡng và try/except | `src/task7_reranking.py`, `src/task8_pageindex_vectorless.py`, `src/task9_retrieval_pipeline.py` | Done |
| Generation + UI | `generate_with_citation()` có safe refusal, Streamlit hiển thị nguồn thật | `src/task10_generation.py`, `app.py` | Done |
| Evaluation | 15 golden case, script A/B, phân tích 3 case kém nhất | `src/run_evaluation.py`, `group_project/evaluation/` | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Nâng `CHUNK_SIZE` từ 500 lên 800 và chunk hai tầng — tách theo heading
   Chương/Điều trước, cắt theo ký tự sau.
   **Lý do/evidence:** Đo 156 Điều trong corpus: trung vị 799 ký tự, chỉ 52/156 Điều vừa
   trong 500 ký tự. Với cấu hình starter, hai phần ba số Điều bị chẻ nhỏ; ví dụ Điều 4 của
   790/QĐ-ĐHCNTT (định nghĩa tín chỉ) dài ~1.700 ký tự bị cắt thành 4 mảnh.
   **Trade-off:** Chunk lớn hơn làm tăng recall nhưng giảm precision vì mỗi chunk mang thêm
   nội dung không liên quan. Số chunk giảm từ ~463 xuống 396.

2. **Quyết định:** Dùng `BM25Plus` thay vì `BM25Okapi`.
   **Lý do/evidence:** Công thức Okapi tính `idf = log(N − n + 0.5) − log(n + 0.5)`, cho đúng
   0 khi term xuất hiện ở một nửa số tài liệu. Trên corpus 2 tài liệu của contract test, toàn
   bộ score về 0 và `test_lexical_search_returns_bm25_contract` không thể pass — kể cả với
   code gợi ý sẵn trong scaffold.
   **Trade-off:** Mất ngưỡng 0 tự nhiên để phát hiện "không khớp gì". Không ảnh hưởng pipeline
   vì Task 9 dùng dense score làm ngưỡng fallback.

## Kiểm thử và kết quả

- **Test tự động:** `pytest tests/ -q` → 20 passed (15 contract + 5 acceptance).
- **Hiệu chỉnh ngưỡng fallback:** 11 truy vấn thủ công. Trong chủ đề 0.6282–0.7391, ngoài chủ
  đề 0.3432–0.4361 → chọn 0.55. Giá trị mặc định 0.3 của starter thấp hơn cả truy vấn ngoài
  chủ đề tệ nhất nên fallback sẽ không bao giờ kích hoạt.
- **A/B trên 15 golden case:** Config A (dense-only) average 0.8178, Config B (hybrid+RRF)
  0.7961, delta −0.0217. Config A thắng cả 4 metric.
- **Lỗi đã phát hiện và cách xử lý:**
  - Đa số PDF trên cổng UIT/ĐHQG/Bộ GD&ĐT là bản scan hoặc OCR bằng font không Unicode, trích
    ra ký tự rác. Viết script sàng 69 PDF theo tỉ lệ ký tự tiếng Việt, giữ lại 24 file dùng được.
  - Văn bản 196/QĐ-ĐHCNTT có 151 ký tự `ƣ` thay `ư`, khiến `đƣợc` không khớp `được` ở cả
    embedding lẫn BM25. Thêm bảng ánh xạ ký tự trong `normalize_text()`.
  - Mục lục của văn bản bị biến thành heading, tạo chunk rỗng cạnh tranh thứ hạng với chunk có
    nội dung. Lọc theo dấu hiệu dot leader.
  - `upsert` không xóa ID cũ: khi đổi `CHUNK_SIZE`, 26 chunk của cấu hình cũ vẫn nằm lại và vẫn
    được search trả về. Thêm bước dọn chunk mồ côi.
  - Nhãn `[Document N]` trong câu trả lời đánh theo thứ tự context sau `reorder_for_llm()`,
    không phải thứ tự `sources`. Lấy thẳng chỉ số thì 3/5 citation trỏ sai nguồn. Sửa bằng
    `citation_numbers()` trong `app.py`.
  - Mở ChromaDB `PersistentClient` từ hai tiến trình cùng lúc làm hỏng file HNSW index, phải
    embed lại toàn bộ corpus. Ghi lưu ý vận hành vào báo cáo.

## Điều còn hạn chế

- **Hạn chế cụ thể:** Retrieval không bắc được cầu giữa viết tắt và dạng đầy đủ. Văn bản 159
  dùng `KLTN` 113 lần so với 11 lần viết đầy đủ, `CBPB` 25 lần so với 2 lần. Câu hỏi viết đầy
  đủ nên cả 5 chunk lấy về đều từ văn bản khác, `context_recall = 0.000`. Có case khác trả lời
  đúng chỉ nhờ may mắn vì văn bản sai tình cờ chứa cùng thông tin.
- **Thay đổi đầu tiên nếu có thêm thời gian:** Đọc bảng thuật ngữ (Điều 2 của mỗi văn bản) rồi
  chèn dạng đầy đủ vào chunk, ví dụ `KLTN (khóa luận tốt nghiệp)`. Xác minh bằng cách chạy lại
  `python -m src.run_evaluation` và kiểm tra `chunk_ids` của case này có xuất hiện
  `legal/159-...` hay không.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại
trong buổi demo.

- Ngày:
- Tên thành viên:
