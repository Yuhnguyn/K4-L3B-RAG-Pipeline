# Individual contribution report

> Báo cáo này chỉ kê phần việc **bản thân trực tiếp làm** trên nền pipeline do
> thành viên khác trong nhóm đã dựng trước. Các module Task 1–10, UI và evaluation
> ban đầu không nằm trong bảng dưới đây.

## Thông tin

- Họ và tên: Nguyễn Phúc Huy
- Mã học viên: 2A202602911
- Nhóm: K4 — L3B
- Repository/branch: `K4-L3B-RAG-Pipeline`, nhánh `main`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Mở rộng viết tắt khi index | Thêm `src/glossary.py`: trích bảng viết tắt từ chính văn bản (Điều 2 của 159, `DANH MỤC TỪ VIẾT TẮT` của 1032/790, câu `(sau đây viết tắt là ...)` của 956), chèn dạng đầy đủ vào cuối chunk lúc chunking | `src/glossary.py`, `src/task4_chunking_indexing.py`, `tests/test_glossary.py` | Done |
| Conversation memory | Thêm `src/conversation_memory.py`: viết lại câu hỏi nối tiếp thành câu hỏi độc lập trước khi retrieve; fallback về câu gốc khi LLM lỗi; nối vào UI | `src/conversation_memory.py`, `app.py`, `tests/test_conversation_memory.py` | Done |
| Sửa lỗi tài liệu | Đồng bộ số chunk 422 → 396, gộp `reports/RESULT.md` về một nguồn, cập nhật README, cho evaluator chạy được với Gemini | `group_project/evaluation/RESULT.md`, `README.md`, `src/run_evaluation.py`, `pyproject.toml` | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Chọn hiện thực đúng Recommendation #1 của báo cáo nhóm — mở rộng viết tắt **ở tầng chunk** thay vì mở rộng truy vấn.
   **Lý do/evidence:** Case *"Khi cán bộ phản biện đánh giá khóa luận tốt nghiệp dưới 5 điểm..."* có `context_recall = 0.000`: cả 5 chunk lấy về đều từ văn bản 790 (viết đầy đủ), trong khi câu trả lời ở 159 — nơi `KLTN` xuất hiện 113 lần so với 11 lần viết đầy đủ, `CBPB` 25 lần so với 2 lần. Chunk `content` là nguồn chung của cả dense (embedding) và BM25 (token), nên chèn ở tầng chunk sửa được cả hai retriever cùng lúc.
   **Trade-off:** Chunk dài thêm một dòng, có thể giảm precision ở vài case vì thêm token không liên quan; phải đo lại toàn bộ 15 case chứ không chỉ case mục tiêu.

2. **Quyết định:** Chèn chú thích ở **cuối chunk** thay vì sửa thẳng trong câu, và **không** đổi chữ ký `generate_with_citation` cho conversation memory.
   **Lý do/evidence:** Báo cáo nhóm đặt nặng trích dẫn đối chiếu được với PDF gốc, nên phần thân phải giữ nguyên văn. Với conversation memory, `tests/test_contracts.py::test_public_function_signatures_are_stable` buộc chữ ký đúng `["query", "top_k"]`; viết lại câu hỏi là bước tiền xử lý ở tầng UI, không phải nhánh retrieval, nên không cần đụng contract.
   **Trade-off:** Chú thích ở cuối chunk có thể bị mô hình trích dẫn lẫn vào câu trả lời; đổi lại không làm sai lệch văn bản nguồn.

## Kiểm thử và kết quả

- **Test tự động:** `pytest -q` → **41 passed** (20 test gốc + 21 test mới: glossary, conversation memory, base_url).
- **Kiểm chứng không cần API:** `chunk_documents()` vẫn cho ra đúng **396 chunk** (ID ổn định, không sinh mồ côi) và **210/396 chunk (53%)** được chèn chú thích; chunk `legal/159-...::chunk-2` nay mang `KLTN = Khóa luận tốt nghiệp`, `CBPB = Cán bộ phản biện`.
- **Mở rộng viết tắt — đo A/B theo đúng quy trình của báo cáo:**
  - Re-index: `python -m src.task4_chunking_indexing` (số chunk giữ nguyên 396 vì ID ổn định).
  - Chấm lại: `python -m src.run_evaluation` → `group_project/evaluation/raw_results_abbrev.json`.
  - Ghi chú về provider: cả baseline lẫn candidate chạy cùng một LLM giám khảo (dùng endpoint OpenAI-compatible, ví dụ Command Code; embeddings `bge-m3` cục bộ) để delta chỉ phản ánh thay đổi retrieval.
  - Bảng before/after 4 metric và `context_recall` của case 12: _(TODO: điền số sau khi chạy)_.
  - Kiểm tra trực tiếp: `chunk_ids` của case 12 phải chứa `legal/159-...`, tức là trước đây không có.
- **Conversation memory — demo hai lượt:**
  - Lượt 1: *"Điều kiện để làm khóa luận tốt nghiệp là gì?"*
  - Lượt 2: *"Thế còn thời gian thực hiện?"* → condense thành *"Thời gian thực hiện khóa luận tốt nghiệp là bao lâu?"*
  - Kết quả retrieve/answer trước và sau khi bật memory: _(TODO: điền sau khi chạy)_.
- **Lỗi đã phát hiện và cách xử lý:**
  - Bảng viết tắt của 790/QĐ-ĐHCNTT bị PDF tách rời khối viết tắt và khối định nghĩa nên parser không ghép cặp 1-1 được; xử lý bằng `MANUAL` có ghi rõ nguồn thay vì ghép cặp mù.
  - Nếu chèn mọi viết tắt 2 ký tự (`SV`, `TV`), gần như mọi chunk đều nhận chú thích và embedding bị loãng; xử lý bằng ngưỡng `MIN_ABBREV_LEN = 3`, vẫn phủ các viết tắt mục tiêu `KLTN`/`CBHD`/`CBPB`.

## Điều còn hạn chế

- **Hạn chế cụ thể:** Việc mở rộng viết tắt mới xử lý được các viết tắt đã có bảng trong văn bản. Viết tắt không được định nghĩa ở đâu (ví dụ một số tên đơn vị) vẫn không khớp được.
- **Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện:** Kiểm tra `context_precision` có bị giảm do chunk dài thêm không; nếu giảm, giới hạn số viết tắt chèn vào mỗi chunk hoặc chèn ở dạng metadata thay vì nối vào `content`.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày:
- Tên thành viên: Nguyễn Phúc Huy
