# Individual contribution report

> Báo cáo này chỉ kê phần việc **bản thân trực tiếp làm** trên nền pipeline do
> thành viên khác trong nhóm đã dựng trước. Các module Task 1–10, UI và evaluation
> ban đầu không nằm trong bảng dưới đây.

## Thông tin

- Họ và tên: Nguyễn Phúc Huy
- Mã học viên: 2A202602911
- Nhóm: K4 — L3B
- Repository/branch: fork `Yuhnguyn/K4-L3B-RAG-Pipeline`, nhánh
  `feat/abbrev-memory-commandcode` (commit `7c3f61e`), PR #1 về `hddung-vinai/K4-L3B-RAG-Pipeline`

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Mở rộng viết tắt khi index | Thêm `src/glossary.py`: trích bảng viết tắt từ chính văn bản (Điều 2 của 159, `DANH MỤC TỪ VIẾT TẮT` của 1032/790, câu `(sau đây viết tắt là ...)` của 956), chèn dạng đầy đủ vào cuối chunk lúc chunking; thêm cờ `GLOSSARY_EXPANSION` để đo A/B | `src/glossary.py`, `src/task4_chunking_indexing.py`, `tests/test_glossary.py` | Done |
| Conversation memory | Thêm `src/conversation_memory.py`: viết lại câu hỏi nối tiếp thành câu hỏi độc lập trước khi retrieve; fallback về câu gốc khi LLM lỗi; nối vào UI, không đổi chữ ký `generate_with_citation` | `src/conversation_memory.py`, `app.py`, `tests/test_conversation_memory.py` | Done |
| Hỗ trợ provider + script so sánh | `task10`/`run_evaluation` nhận `OPENAI_BASE_URL` và tách evaluator embeddings; thêm `src/compare_evaluation.py` để so hai lần chạy | `src/task10_generation.py`, `src/run_evaluation.py`, `src/compare_evaluation.py`, `tests/test_llm_provider.py` | Done |
| Sửa lỗi tài liệu | Đồng bộ số chunk 422 → 396, gộp `reports/RESULT.md` về một nguồn, cập nhật README | `group_project/evaluation/RESULT.md`, `README.md`, `pyproject.toml` | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Chọn hiện thực đúng Recommendation #1 của báo cáo nhóm — mở rộng viết tắt **ở tầng chunk** thay vì mở rộng truy vấn.
   **Lý do/evidence:** Case 12 *"Khi cán bộ phản biện đánh giá khóa luận tốt nghiệp dưới 5 điểm..."* có `context_recall = 0.000` ở cả hai config: cả 5 chunk lấy về đều từ văn bản 790 (viết đầy đủ), trong khi câu trả lời ở 159 — nơi `KLTN` xuất hiện 113 lần so với 11 lần viết đầy đủ, `CBPB` 25 lần so với 2 lần. Chunk `content` là nguồn chung của cả dense (embedding) và BM25 (token), nên chèn ở tầng chunk sửa được cả hai retriever cùng lúc.
   **Trade-off:** Chunk dài thêm một dòng, có thể giảm precision ở vài case vì thêm token không liên quan; phải đo lại toàn bộ 15 case chứ không chỉ case mục tiêu.

2. **Quyết định:** Chèn chú thích ở **cuối chunk** thay vì sửa thẳng trong câu, và **không** đổi chữ ký `generate_with_citation` cho conversation memory.
   **Lý do/evidence:** Báo cáo nhóm đặt nặng trích dẫn đối chiếu được với PDF gốc, nên phần thân phải giữ nguyên văn. Với conversation memory, `tests/test_contracts.py::test_public_function_signatures_are_stable` buộc chữ ký đúng `["query", "top_k"]`; viết lại câu hỏi là bước tiền xử lý ở tầng UI, không phải nhánh retrieval, nên không cần đụng contract.
   **Trade-off:** Chú thích ở cuối chunk có thể bị mô hình trích dẫn lẫn vào câu trả lời; đổi lại không làm sai lệch văn bản nguồn.

## Kiểm thử và kết quả

### Test tự động

`pytest -q` → **42 passed** (20 test gốc + 22 test mới: glossary 11, conversation memory 7, base_url 3, cờ `GLOSSARY_EXPANSION` 1).

### Mở rộng viết tắt — bằng chứng đã đo

- `chunk_documents()` vẫn cho ra đúng **396 chunk** (ID ổn định theo `::chunk-<index>`, re-index ghi đè tại chỗ nên không sinh mồ côi).
- **210/396 chunk (53%)** được chèn chú thích viết tắt.
- Ví dụ chunk `legal/159-2024-quy-dinh-khoa-luan-tot-nghiep.md::chunk-2` nay kết thúc bằng:
  `[Từ viết tắt: CBHD = Cán bộ hướng dẫn; CBPB = Cán bộ phản biện; KLTN = Khóa luận tốt nghiệp; P.ĐTĐH = Phòng Đào tạo Đại học; ...]`

**Trạng thái trước khi sửa** — lấy từ baseline có sẵn `group_project/evaluation/raw_results.json`
(commit `6a2a2d4`, generator/evaluator `gpt-4o-mini`), case 12:

| Chỉ số | Config A (dense-only) | Config B (hybrid+RRF) |
|---|---:|---:|
| `context_recall` | **0.000** | **0.000** |
| `context_precision` | 0.700 | 0.950 |
| `answer_relevancy` | 0.000 | 0.000 |
| 159 có trong top-5? | không | không |
| `chunk_ids` (đầu) | `790::chunk-101/102/99` | `790::chunk-101/102/98` |

Cả hai config đều lấy toàn chunk từ 790 và trả lời bằng safe refusal — khớp đúng phân tích
"bất đối xứng viết tắt" trong `RESULT.md`.

**Trạng thái sau khi sửa: chưa đo.** Việc này cần tải `BAAI/bge-m3` (~2.3GB) và chạy
`run_evaluation` hai lượt; nhóm chưa thực hiện trong phạm vi thời gian này. Lệnh tái lập:

```bash
GLOSSARY_EXPANSION=0 python -m src.task4_chunking_indexing
GLOSSARY_EXPANSION=0 python -m src.run_evaluation
cp group_project/evaluation/raw_results.json raw_results_baseline.json

GLOSSARY_EXPANSION=1 python -m src.task4_chunking_indexing
GLOSSARY_EXPANSION=1 python -m src.run_evaluation

python -m src.compare_evaluation raw_results_baseline.json group_project/evaluation/raw_results.json
```

Tiêu chí đạt: `chunk_ids` của case 12 xuất hiện `legal/159-...` và `context_recall` tăng
khỏi 0.000. Lưu ý phương pháp: phải chạy **cả hai lượt bằng cùng một LLM giám khảo**
(ở đây dùng `OPENAI_BASE_URL` trỏ endpoint OpenAI-compatible + embeddings `bge-m3` cục bộ),
không so với số `gpt-4o-mini` cũ.

### Conversation memory — bằng chứng đã đo

Chạy thật `condense_question()` với LLM qua endpoint OpenAI-compatible (Command Code,
model `deepseek/deepseek-v4.1-flash`):

| Lịch sử | Câu hỏi gốc | Sau khi condense |
|---|---|---|
| Lượt 1: *"Điều kiện để làm khóa luận tốt nghiệp là gì?"* | *"Thế còn thời gian thực hiện?"* | *"Thời gian thực hiện khóa luận tốt nghiệp theo quy định là bao lâu?"* |
| như trên | *"Điều kiện để làm khóa luận tốt nghiệp là gì?"* (đã độc lập) | giữ nguyên (không gọi LLM sửa) |

Điểm phương pháp: golden dataset gồm các câu đơn, mỗi case chạy với lịch sử rỗng, nên
conversation memory **không làm thay đổi** số RAGAS của phần A/B ở trên; nó chỉ tác động
lên câu hỏi nối tiếp trong UI.

### Provider — bằng chứng đã đo

Key provider (Command Code) được kiểm chứng: `GET /provider/v1/models` → HTTP 200, 81 model,
có `deepseek/deepseek-v4.1-flash`; `call_llm()` qua repo trả về kết quả hợp lệ. Endpoint này
không có API embeddings nên RAGAS dùng `bge-m3` cục bộ (`EVALUATOR_EMBEDDING_PROVIDER=sentence_transformers`).

### Lỗi đã phát hiện và cách xử lý

- Bảng viết tắt của 790/QĐ-ĐHCNTT bị PDF tách rời khối viết tắt và khối định nghĩa nên parser không ghép cặp 1-1 được; xử lý bằng `MANUAL` có ghi rõ nguồn thay vì ghép cặp mù.
- Nếu chèn mọi viết tắt 2 ký tự (`SV`, `TV`), gần như mọi chunk đều nhận chú thích và embedding bị loãng; xử lý bằng ngưỡng `MIN_ABBREV_LEN = 3`, vẫn phủ các viết tắt mục tiêu `KLTN`/`CBHD`/`CBPB`.
- Parser câu nội tuyến của 956 ban đầu hút cả cụm dẫn *"bao gồm:"* vào định nghĩa; sửa bằng cách loại `:` và `;` khỏi vế mở rộng.

## Điều còn hạn chế

- **Hạn chế cụ thể:** Chưa có số RAGAS của lượt "sau khi sửa" — mới có bằng chứng cấu trúc (396 chunk, 53% chunk được chèn) và số baseline "trước". Vì vậy chưa khẳng định được mức cải thiện `context_recall` thực tế.
- **Hạn chế thứ hai:** Việc mở rộng viết tắt mới xử lý được các viết tắt đã có bảng trong văn bản. Viết tắt không được định nghĩa ở đâu (ví dụ một số tên đơn vị) vẫn không khớp được.
- **Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện:** Chạy lượt đo "sau" theo đúng lệnh ở trên; nếu `context_precision` giảm do chunk dài thêm, giới hạn số viết tắt chèn vào mỗi chunk hoặc chuyển chú thích sang metadata thay vì nối vào `content`.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 2026-09-25
- Tên thành viên: Nguyễn Phúc Huy
