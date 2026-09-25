# RAG evaluation results

## Run information

| Field                              | Value |
| ---------------------------------- | ----- |
| Evaluation date                    | 2026-09-24 |
| Framework and version              | RAGAS 0.4.3 |
| Evaluator model                    | `gpt-4o-mini` (temperature 0.0), embeddings `text-embedding-3-small` |
| Generator model                    | `gpt-4o-mini` (temperature 0.3, top_p 0.9, max_tokens 1024) |
| Embedding model                    | `BAAI/bge-m3`, 1024 chiều, normalize |
| Corpus version/commit              | commit `6a2a2d4`; 13 file standardized, sha256 `29f94f278521eb3b`; 396 chunks trong ChromaDB |
| Golden dataset size                | 15 case (5 keyword / 5 semantic / 5 confusable) |
| `top_k`                            | 5 (mỗi nhánh retrieval lấy 10 ứng viên) |
| Fallback threshold and calibration | 0.55, hiệu chỉnh bằng 6 truy vấn trong chủ đề (0.6282–0.7391) và 5 ngoài chủ đề (0.3432–0.4361) — chi tiết ở mục *Fallback threshold* |

Kết quả thô từng case: `group_project/evaluation/raw_results.json`.
Script tái lập: `python -m src.run_evaluation`.

> **Lưu ý về mô hình dùng khi demo.** Toàn bộ số liệu trong báo cáo này được đo với
> generator và evaluator là `gpt-4o-mini`. Tại thời điểm demo, tài khoản OpenAI của nhóm
> hết credit nên bản chạy trực tiếp có thể được chuyển tạm sang `LLM_PROVIDER=gemini`
> bằng cách đổi `.env`, không sửa code. Khác biệt này **chỉ nằm ở tầng generation**:
> embedding vẫn là `bge-m3` chạy cục bộ, ChromaDB, cấu hình chunk, BM25, RRF và ngưỡng
> fallback đều không đổi, nên mọi kết luận về retrieval trong báo cáo vẫn giữ nguyên
> hiệu lực. Các số về `faithfulness` và `answer relevance` thì gắn với `gpt-4o-mini`
> và cần đo lại nếu nhóm quyết định đổi hẳn sang mô hình khác.

## Indexing configuration and rationale

Phần này ghi lại giá trị thực dùng ở Task 4–6 và lý do chọn. Mọi số liệu đo trên corpus
tại `data/standardized/` (6 văn bản quy chế UIT + 7 bài viết, 208.766 ký tự).

### Tham số chunking

| Tham số | Giá trị starter | Giá trị nhóm dùng |
| ------------------- | --------------- | ----------------- |
| `CHUNK_SIZE`        | 500             | **800**           |
| `CHUNK_OVERLAP`     | 50              | **120**           |
| `CHUNKING_METHOD`   | `recursive`     | **`markdown_header + recursive`** |
| Số chunk tạo ra     | ~463 (ước lượng) | **396**          |

**Vì sao 800 thay vì 500.** Đơn vị ngữ nghĩa của văn bản pháp quy là một "Điều".
Corpus có 156 Điều với phân phối độ dài:

| Thống kê | Giá trị |
| ------------- | ------- |
| Trung bình    | 1.195 ký tự |
| Trung vị      | 799 ký tự |
| Phân vị 90    | 3.014 ký tự |
| Dài nhất      | 13.077 ký tự |
| Vừa trong 500 ký tự | 52/156 Điều |
| Vừa trong 800 ký tự | 78/156 Điều |

Với `CHUNK_SIZE = 500`, hai phần ba số Điều bị chẻ nhỏ. Ví dụ cụ thể: Điều 4 của Quy chế
790/QĐ-ĐHCNTT (định nghĩa tín chỉ học tập) dài khoảng 1.700 ký tự, bị cắt thành 4 mảnh;
câu hỏi "một tín chỉ bằng bao nhiêu tiết lý thuyết" có thể trúng mảnh chứa định nghĩa
chung mà không chứa con số 15 tiết. Chọn 800 để trung vị một Điều nằm trọn trong một chunk.

Đây là đánh đổi có thật chứ không phải cấu hình tối ưu tuyệt đối: chunk lớn hơn làm tăng
recall nhưng giảm precision, vì mỗi chunk mang theo nhiều nội dung không liên quan tới câu
hỏi. `CHUNK_OVERLAP` nâng lên 120 (giữ tỉ lệ 15% như starter) để phần tiếp giáp giữa hai
mảnh của cùng một Điều dài không bị mất.

**Vì sao chunk hai tầng.** Tầng một dùng `MarkdownHeaderTextSplitter` tách theo heading
`#` (Chương) và `##` (Điều) mà Task 3 đã khôi phục; tầng hai dùng
`RecursiveCharacterTextSplitter` cắt tiếp những mảnh vượt `CHUNK_SIZE`. Chỉ dùng tầng một
là không đủ vì Điều dài nhất tới 13.077 ký tự. Chỉ dùng tầng hai thì ranh giới chunk rơi
ngẫu nhiên vào giữa các Điều.

**Gắn lại tiêu đề Điều vào chunk con.** Khi một Điều bị cắt thành nhiều chunk, chỉ chunk
đầu tiên chứa dòng `## Điều N. ...`. Các chunk sau được chèn lại dòng tiêu đề này ở đầu;
nếu không, chunk chứa nội dung của Điều 4 sẽ không có bất kỳ dấu hiệu nào cho biết nó
thuộc Điều 4, làm hỏng cả dense retrieval lẫn truy vấn BM25 dạng "Điều 4 quy định gì".
Ngân sách ký tự của tầng hai được trừ đi độ dài tiêu đề để chunk cuối cùng không vượt
ngưỡng `CHUNK_SIZE * 1.1` mà contract test kiểm.

### Embedding

| Hạng mục | Giá trị |
| ---------- | ------- |
| Provider   | `sentence_transformers` |
| Model      | `BAAI/bge-m3` |
| Số chiều   | 1.024 |
| Chuẩn hóa  | `normalize_embeddings=True` |

`bge-m3` là model đa ngôn ngữ, xử lý tiếng Việt có dấu tốt và chạy offline nên không phụ
thuộc quota API. Vector được chuẩn hóa để khớp với không gian cosine của ChromaDB.

`embed_texts()` là điểm dùng chung: Task 4 embed corpus, Task 5 embed query bằng đúng hàm
đó. Model được cache ở module level, vì khởi tạo lại `SentenceTransformer` trong mỗi lần
gọi sẽ làm mỗi truy vấn ở Task 5 mất vài giây.

### Chống trùng lặp khi index lại

`collection.upsert()` ghi đè các ID trùng nhưng **không** xóa ID cũ không còn xuất hiện.
Hệ quả: nếu đổi `CHUNK_SIZE` từ 500 lên 800, số chunk giảm từ khoảng 463 xuống 396, và
khoảng 40 chunk cũ có `chunk_index` cao vẫn nằm lại trong ChromaDB. Chúng trở thành dữ
liệu mồ côi được sinh bởi một cấu hình chunking đã bị thay thế, nhưng vẫn được search trả
về và vẫn đi vào ngữ cảnh của LLM.

`index_to_vectorstore()` vì vậy làm thêm một bước sau khi upsert: lấy toàn bộ ID hiện có
trong collection, giữ lại những ID thuộc các document vừa được ghi, và xóa phần chênh lệch
so với tập ID mới. Điều kiện "index lại mà không nhân bản dữ liệu" của checkpoint chỉ đạt
được nhờ bước này, không phải nhờ riêng `upsert`.

ID chunk có dạng `<đường dẫn tương đối>::chunk-<index>`, ví dụ
`legal/790-2022-quy-che-dao-tao-tin-chi.md::chunk-12`. Dạng này ổn định giữa các lần chạy
và cho phép truy ngược từ một chunk về file standardized, rồi qua frontmatter về file
landing và URL công khai.

### Metadata

Mỗi chunk mang `source`, `title`, `doc_type`, `url`, `chunk_index` theo
`docs/MODULE_CONTRACTS.md`. Metadata được đọc từ YAML frontmatter mà Task 3 nhúng vào file
Markdown, không suy ra từ tên file — nhờ đó `title` là tên văn bản đầy đủ kèm số hiệu
("Quy chế đào tạo theo học chế tín chỉ... (790/QĐ-ĐHCNTT, 28/9/2022)") thay vì tên file
không dấu. Khối frontmatter bị loại khỏi `content` trước khi chunk, nếu không thì chunk
đầu của mỗi tài liệu sẽ toàn metadata và embedding vô nghĩa.

Một khác biệt giữa contract và ChromaDB cần xử lý: contract cho phép `url: str | None`,
nhưng ChromaDB từ chối giá trị `None` trong metadata. `None` được chuyển thành chuỗi rỗng
khi upsert.

### Lexical search (BM25)

| Hạng mục | Lựa chọn |
| ---------- | -------- |
| Thuật toán | `BM25Plus` |
| Tokenizer  | regex giữ chữ có dấu, số, và token ghép bằng `/` hoặc `-` |
| Nguồn corpus | đọc lại chunk từ ChromaDB |

**Vì sao BM25Plus thay vì BM25Okapi.** `BM25Okapi` trong `rank_bm25` tính
`idf = log(N - n + 0.5) - log(n + 0.5)`. Với term xuất hiện ở đúng một nửa số tài liệu,
idf bằng 0 và toàn bộ score về 0 — corpus càng nhỏ càng dễ rơi vào trường hợp này.
`BM25Plus` (Lv & Zhai, 2011) thêm cận dưới nên xếp hạng vẫn đúng. Đánh đổi: không còn
ngưỡng 0 tự nhiên để phát hiện "không khớp gì", nhưng Task 9 dùng dense score làm ngưỡng
fallback nên điều này không ảnh hưởng tới pipeline.

**Vì sao tokenizer riêng.** Giá trị của BM25 trong corpus này nằm ở việc khớp chính xác mã
văn bản và số hiệu: `790/QĐ-ĐHCNTT`, `Điều 12`, `TOEIC 450`. Tách token bằng khoảng trắng
thuần thì `Điều 5.` thành token `5.` không khớp với `5`; tách bỏ hết dấu câu thì
`790/QĐ-ĐHCNTT` vỡ thành ba mảnh vô dụng. Tokenizer giữ nguyên token ghép **và** tách thêm
các thành phần con, nên cả truy vấn `790/QĐ-ĐHCNTT` lẫn truy vấn `790` đều khớp.

Hạn chế đã biết: tiếng Việt tách âm tiết bằng khoảng trắng, nên token là âm tiết chứ không
phải từ ("học phần" thành hai token). Điều này làm BM25 nhiễu hơn so với tiếng Anh. Nhóm
chưa dùng word segmentation ở phase này; nếu context precision thấp ở phần đánh giá, đây
là hướng cải thiện đầu tiên nên thử.

**Nguồn corpus.** `CORPUS` được nạp lại từ chính ChromaDB thay vì chunk lại từ Markdown.
Chunk lại sẽ tạo ra hai tập chunk khác nhau giữa dense và BM25, khiến RRF ở Task 7 không
ghép được theo ID.

## Retrieval pipeline and fallback calibration

### RRF

| Tham số | Giá trị |
| ------- | ------- |
| Công thức | `RRF(d) = Σ 1 / (k + rank)`, rank bắt đầu từ 1 |
| `k` | 60 |
| Số lần fuse mỗi truy vấn | 1 |
| Ứng viên lấy từ mỗi nhánh | `top_k × 2` |

Dense similarity và BM25 score không cộng trực tiếp được. Số đo thực tế trên corpus
này: dense trả về 0.6031 / 0.5849 / 0.5837 còn BM25 trả về 21.0190 / 20.2030 / 20.1764
cho cùng một truy vấn. Cộng thẳng thì BM25 áp đảo hoàn toàn; chuẩn hóa min-max cũng
không ổn định vì phân phối hai bên thay đổi theo từng truy vấn. RRF bỏ hẳn độ lớn và
chỉ dùng thứ hạng.

`k = 60` làm phẳng chênh lệch giữa các hạng đầu: rank 1 đóng góp 1/61 ≈ 0.01639, rank 2
đóng góp 1/62 ≈ 0.01613. Nhờ vậy một chunk có mặt ở cả hai danh sách (ví dụ rank 2 dense
+ rank 1 BM25 = 0.03252) luôn thắng một chunk chỉ dẫn đầu một danh sách (0.01639).

**Không sửa trực tiếp item đầu vào.** `rerank_rrf()` gọi `.copy()` trước khi ghi `score`
và `retrieval_method`. Lý do không phải là sạch code: Task 9 đọc cosine score gốc từ
danh sách dense để quyết định fallback. Nếu RRF ghi đè score lên chính item của danh
sách dense thì 0.6031 bị thay bằng 0.0325, và vì RRF score luôn ở mức ~0.03 nên **mọi
truy vấn đều rơi xuống dưới threshold và fallback kích hoạt vô điều kiện**. Lỗi này
không làm test nào đỏ nhưng phá toàn bộ logic fallback. Task 9 còn phòng thêm một lớp
bằng cách đọc `best_dense_score` trước khi gọi RRF.

### Fallback threshold

| Hạng mục | Giá trị |
| ---------- | ------- |
| `SCORE_THRESHOLD` | **0.55** |
| Score dùng để so sánh | cosine similarity cao nhất của dense search |
| Score **không** dùng | RRF score |

Hiệu chỉnh bằng 11 truy vấn trên corpus 396 chunk, model `bge-m3`:

| Nhóm | Truy vấn | Best dense score |
| ---- | -------- | ---------------: |
| Trong chủ đề | Sinh viên bị buộc thôi học trong trường hợp nào? | 0.7391 |
| Trong chủ đề | Một tín chỉ học tập bằng bao nhiêu tiết lý thuyết? | 0.7363 |
| Trong chủ đề | Điều kiện được làm khóa luận tốt nghiệp là gì? | 0.7259 |
| Trong chủ đề | Thủ tục phúc khảo bài thi như thế nào? | 0.7046 |
| Trong chủ đề | Chương trình tài năng tuyển sinh ra sao? | 0.6523 |
| Trong chủ đề | Chuẩn ngoại ngữ đầu ra của sinh viên UIT là gì? | 0.6282 |
| Ngoài chủ đề | Hướng dẫn thay lốp xe ô tô | 0.4361 |
| Ngoài chủ đề | Giá Bitcoin hôm nay là bao nhiêu | 0.4256 |
| Ngoài chủ đề | Lịch thi đấu bóng đá Ngoại hạng Anh | 0.4190 |
| Ngoài chủ đề | Triệu chứng của bệnh cúm mùa | 0.3723 |
| Ngoài chủ đề | Cách nấu phở bò ngon tại nhà | 0.3432 |

Hai nhóm tách bạch: trong chủ đề 0.6282–0.7391, ngoài chủ đề 0.3432–0.4361, khoảng
trống 0.4361–0.6282. Chọn 0.55 nằm giữa khoảng trống, cách mép trên nhóm ngoài chủ đề
0.11 và mép dưới nhóm trong chủ đề 0.08.

**Giá trị mặc định 0.3 của starter không dùng được cho corpus này**: nó thấp hơn cả truy
vấn ngoài chủ đề tệ nhất (0.3432), nên fallback sẽ không bao giờ kích hoạt và hệ thống
trả lời câu hỏi nấu phở bằng quy chế đào tạo. Đây là minh chứng cho việc không có
threshold đúng cho mọi corpus: 0.55 chỉ đúng với corpus này, model `bge-m3` này và cấu
hình chunk 800/120. Thay bất kỳ yếu tố nào cũng phải đo lại.

Kiểm chứng end-to-end sau khi đặt threshold:

| Truy vấn | `retrieval_method` trả về |
| -------- | ------------------------- |
| Sinh viên bị buộc thôi học trong trường hợp nào? | `hybrid` |
| Một tín chỉ học tập bằng bao nhiêu tiết lý thuyết? | `hybrid` |
| Cách nấu phở bò ngon tại nhà | `pageindex` |

### Vectorless fallback (Task 8)

Nhóm **không** gọi dịch vụ PageIndex từ xa mà tự cài đặt vectorless retriever chạy cục
bộ. Lý do: chưa có `PAGEINDEX_API_KEY` nên đường remote không chạy được và phần so sánh
sẽ trống; đồng thời corpus là văn bản pháp quy đã có sẵn cây `# CHƯƠNG` / `## Điều` do
Task 3 khôi phục — đúng loại dữ liệu mà điều hướng theo cấu trúc phát huy tác dụng.

Cây gồm 13 documents, 156 nodes, cache ở `chroma_db/pageindex_tree.json`. Tìm kiếm hai
tầng, không dùng embedding: tầng một chọn nhánh tài liệu theo độ khớp với tiêu đề văn
bản và tiêu đề các Điều; tầng hai chấm điểm từng node Điều với trọng số 3 cho khớp ở
tiêu đề và 1 cho khớp trong thân bài.

Hai lần sửa trong quá trình hiệu chỉnh, cả hai đều phát hiện bằng cách chạy thật:

1. **Thiên lệch độ dài.** Đếm token trần làm bài news dài 3.000 ký tự đứng trên đúng
   Điều cần tìm, chỉ vì nó chứa nhiều token hơn. Khắc phục bằng cách chia phần điểm thân
   bài cho căn bậc hai số token riêng biệt, cùng ý tưởng length normalization của BM25.
2. **Mọi token đếm ngang nhau.** Sau khi chuẩn hóa độ dài, truy vấn "sinh viên bị buộc
   thôi học" lại bị Điều hành chính chung chung chiếm chỗ, vì "sinh", "viên", "học" có
   mặt ở gần như mọi Điều. Khắc phục bằng trọng số IDF tính trên tập 156 node. Sau đó
   truy vấn này trả về đúng "Điều 17. Thôi học, tạm dừng học tập".

**Hạn chế đã đo và không che giấu:** vectorless fallback không tự phân biệt được truy vấn
trong hay ngoài chủ đề. Điểm thô cao nhất của 5 truy vấn trong chủ đề là 17.76–46.85,
của 5 truy vấn ngoài chủ đề là 8.26–18.69 — **hai khoảng chồng lên nhau**. Cụ thể
"Hướng dẫn thay lốp xe ô tô" đạt 18.69, cao hơn "Sinh viên bị buộc thôi học" ở 17.76,
vì nó khớp cụm "hướng dẫn". Nhóm đã cân nhắc thêm ngưỡng tối thiểu cho fallback nhưng
**không có giá trị nào tách được hai nhóm**, nên không thêm.

Hệ quả thực tế: với câu "Cách nấu phở bò ngon tại nhà", fallback vẫn trả về "Điều 24.
Cách quản lý điểm" do khớp chữ "cách". Đây là lý do kiến trúc đặt quyết định tin cậy ở
dense score (nơi hai nhóm tách bạch rõ) và đặt việc từ chối trả lời ở tầng generation
của Task 10, chứ không dựa vào fallback tự lọc.

### Xử lý lỗi provider

`retrieve()` bọc `pageindex_search()` trong `try/except`. Khi fallback ném lỗi, pipeline
in cảnh báo và trả về hybrid result đang có thay vì dừng. Hành vi này được contract test
`test_retrieve_survives_fallback_provider_error` kiểm bằng cách ném `RuntimeError`.

## Generation (Task 10)

| Hạng mục | Giá trị |
| ---------- | ------- |
| Provider | `openai` |
| Model | `gpt-4o-mini` (mặc định khi `LLM_MODEL` trống) |
| `temperature` | 0.3 |
| `top_p` | 0.9 |
| `max_tokens` | 1024 |
| Timeout | 60s |
| `top_k` | 5 |

### Chống lost-in-the-middle

`reorder_for_llm()` xếp xen kẽ thay vì giữ thứ tự score giảm dần. LLM nhớ rõ phần đầu và
phần cuối context, phần giữa dễ bỏ sót; nếu giữ nguyên thứ tự thì chunk mạnh thứ hai và
thứ ba rơi đúng vào vùng mù.

```
Đầu vào (theo score): [0, 1, 2, 3, 4]
front = [0, 2, 4],  back đảo = [3, 1]
Kết quả:              [0, 2, 4, 3, 1]
```

Chunk mạnh nhất ở đầu, mạnh nhì ở cuối, yếu nhất bị đẩy vào giữa. Hàm không sửa list đầu
vào để `sources` trả về vẫn giữ thứ tự theo score.

### Safe refusal

Đây là chốt chặn cuối cùng của hệ thống. Phần trên đã ghi nhận vectorless fallback không
tự phân biệt được truy vấn trong hay ngoài chủ đề, nên câu hỏi ngoài phạm vi vẫn nhận
được context trông có vẻ liên quan.

Cơ chế: system prompt yêu cầu LLM trả về đúng một chuỗi đánh dấu khi context không chứa
câu trả lời. Pipeline nhận ra chuỗi đó và trả về refusal **kèm `sources: []`** — không
đính kèm nguồn không liên quan, vì trích dẫn sai còn nguy hiểm hơn là không trích dẫn.

Ba đường dẫn tới refusal: `retrieve()` rỗng, LLM báo thiếu evidence, hoặc provider ném
lỗi (hết quota, timeout, mất mạng).

### Kiểm chứng end-to-end

| Truy vấn | `retrieval_source` | Số nguồn | Kết quả |
| -------- | ------------------ | -------: | ------- |
| Một tín chỉ học tập bằng bao nhiêu tiết lý thuyết? | `hybrid` | 5 | Trả lời đúng, cite Điều 4 |
| Sinh viên bị buộc thôi học trong trường hợp nào? | `hybrid` | 5 | Trả lời đúng, cite Điều 16 |
| Cách nấu phở bò ngon tại nhà | `none` | 0 | Từ chối |

Đối chiếu thủ công với văn bản gốc:

- Câu 1 — "15 tiết học lý thuyết" khớp đúng nguyên văn Điều 4 của 790/QĐ-ĐHCNTT.
- Câu 2 — ba trường hợp nêu ra khớp đúng nguyên văn Điều 16 khoản 3a. **Tuy nhiên văn
  bản gốc liệt kê 7 trường hợp, câu trả lời chỉ nêu 3.** Không bịa đặt nhưng thiếu. Đây
  là lỗi recall ở tầng generation chứ không phải retrieval, vì cả 7 trường hợp đều nằm
  trong chunk đã được đưa vào context. Cần theo dõi ở phần đánh giá: nhiều khả năng
  điểm Faithfulness sẽ cao trong khi Answer relevance thấp hơn.

### Chi tiết contract cần lưu ý

`retrieval_method` có 4 giá trị (`dense`/`bm25`/`hybrid`/`pageindex`) nhưng
`retrieval_source` chỉ nhận 3 (`hybrid`/`pageindex`/`none`). Nhánh dense-only của
Config A trả về method `dense`, nên `generate_with_citation()` phải map chứ không gán
thẳng — gán thẳng sẽ vi phạm `validate_generation_result` ngay khi chạy A/B.

## Giao diện Streamlit

`app.py` gọi `generate_with_citation(query, top_k)` và hiển thị câu trả lời kèm toàn bộ
nguồn thật trong `sources`: tên văn bản, score, `retrieval_method`, ID chunk, file landing
và URL công khai. Không hiển thị URL do model tự sinh.

Lịch sử trong `st.session_state` lưu cả `sources` và `retrieval_source` cho từng message
chứ không chỉ phần text, nên nguồn của các câu trả lời trước vẫn render lại được sau mỗi
lần rerun.

### Lỗi ánh xạ citation đã phát hiện và khắc phục

`sources` trong `GenerationResult` được sắp theo score giảm dần vì
`validate_search_results` yêu cầu như vậy. Nhưng context đưa cho LLM lại đi qua
`reorder_for_llm()` để chống lost-in-the-middle, nên **hai thứ tự khác nhau**. Nhãn
`[Document N]` trong câu trả lời đánh theo thứ tự context, không phải thứ tự `sources`.

Với `top_k = 5`, ánh xạ thực tế:

| Nhãn trong câu trả lời | Nếu coi là `sources[N-1]` | Thực tế |
| ---------------------- | ------------------------- | ------- |
| `[Document 1]` | chunk-0 | chunk-0 |
| `[Document 2]` | chunk-1 | **chunk-2** |
| `[Document 3]` | chunk-2 | **chunk-4** |
| `[Document 4]` | chunk-3 | chunk-3 |
| `[Document 5]` | chunk-4 | **chunk-1** |

Tức là **3/5 citation sẽ trỏ sai nguồn** nếu lấy thẳng chỉ số. Đây là lỗi im lặng: giao
diện vẫn chạy, vẫn hiện nguồn, chỉ là nguồn sai — đúng loại lỗi mà người chấm khó phát
hiện nhưng phá vỡ toàn bộ tính kiểm chứng được.

`app.py` khắc phục bằng hàm `citation_numbers()`: dựng lại đúng thứ tự context bằng
`reorder_for_llm(sources)` rồi gắn số `[Document N]` tương ứng vào từng nguồn hiển thị.

### Kiểm chứng end-to-end qua UI

Chạy `app.py` headless bằng `streamlit.testing.v1.AppTest` và gửi thật hai truy vấn:

| Truy vấn | `retrieval_source` | Số nguồn | Kết quả UI |
| -------- | ------------------ | -------: | ---------- |
| Sinh viên bị buộc thôi học trong trường hợp nào? | `hybrid` | 5 | Câu trả lời + 5 expander nguồn, mỗi nguồn có link PDF gốc |
| Cách nấu phở bò ngon tại nhà | `none` | 0 | Safe refusal + thông báo không dựa trên nguồn nào |

Không có exception ở cả hai lượt. Thứ tự nhãn hiển thị là `[Document 1] [Document 5]
[Document 2] [Document 4] [Document 3]` — không liên tục, đúng như kỳ vọng vì nguồn được
sắp theo score còn nhãn theo thứ tự context. Đây là bằng chứng ánh xạ đã hoạt động.

Lịch sử sau hai lượt giữ đúng `sources=5 / retrieval_source=hybrid` cho câu đầu và
`sources=0 / retrieval_source=none` cho câu sau.

### Lưu ý vận hành

Không chạy `app.py` cùng lúc với `task4_chunking_indexing`. ChromaDB `PersistentClient`
không an toàn khi hai tiến trình cùng mở một thư mục — nhóm đã làm hỏng file HNSW index
một lần vì lỗi này và phải embed lại toàn bộ corpus.

## Configurations

- **Config A — dense-only:** `retrieve(query, top_k=5, use_reranking=False)`. Lấy top-10 ứng viên bằng dense search trên ChromaDB (cosine, `bge-m3`), trả thẳng 5 chunk đầu theo cosine score giảm dần. Không dùng BM25 để xếp hạng, không fuse.
- **Config B — hybrid + RRF:** `retrieve(query, top_k=5, use_reranking=True)`. Lấy top-10 từ dense và top-10 từ BM25Plus trên cùng tập 396 chunk, fuse một lần bằng RRF (`k = 60`, rank từ 1), trả 5 chunk có RRF score cao nhất.

Mọi yếu tố khác giữ nguyên giữa hai config: cùng 15 golden case, cùng generator `gpt-4o-mini`
(temperature 0.3), cùng `SYSTEM_PROMPT`, cùng evaluator `gpt-4o-mini` (temperature 0.0),
cùng `top_k = 5`, cùng `SCORE_THRESHOLD = 0.55`, cùng corpus và cùng cấu hình chunk 800/120.
Chỉ bước hợp nhất xếp hạng thay đổi.

## Overall scores

| Metric            | Config A | Config B | Delta B−A |
| ----------------- | -------: | -------: | --------: |
| Faithfulness      |   1.0000 |   0.9643 |   −0.0357 |
| Answer relevance  |   0.4426 |   0.4345 |   −0.0081 |
| Context recall    |   0.9238 |   0.8952 |   −0.0286 |
| Context precision |   0.9047 |   0.8903 |   −0.0144 |
| **Average**       | **0.8178** | **0.7961** | **−0.0217** |

Phân rã theo loại câu hỏi:

| Loại | n | Metric | Config A | Config B |
| ---- | -: | ------ | -------: | -------: |
| keyword | 5 | faithfulness | 1.000 | 0.900 |
| keyword | 5 | context precision | 0.890 | 0.840 |
| semantic | 5 | answer relevance | 0.432 | 0.344 |
| semantic | 5 | context recall | 0.971 | 0.886 |
| confusable | 5 | context recall | 0.800 | 0.800 |
| confusable | 5 | answer relevance | 0.462 | 0.517 |

## A/B comparison

**Cấu hình tốt hơn: Config A (dense-only).** Đây là kết quả âm tính đối với giả thuyết ban
đầu của nhóm, và nhóm giữ nguyên kết luận này thay vì chọn Config B cho "đẹp báo cáo".

**Evidence.** Config A thắng trên cả bốn metric, nhưng không phải chênh lệch nào cũng có ý
nghĩa như nhau:

- **Context recall (−0.0286) là chênh lệch đáng tin nhất và có nguyên nhân truy được.** Ở
  case *"Sinh viên bị đuổi học trong những trường hợp nào?"*, recall tụt từ 0.857 (A) xuống
  0.429 (B). Đối chiếu chunk ID: Config A lấy được `790::chunk-57` chứa đúng danh sách các
  trường hợp buộc thôi học; Config B đẩy chunk đó ra khỏi top-5 và thay bằng
  `1139::chunk-75` — *"Điều 23. Xử lý sinh viên dự thi vi phạm quy định"* của một văn bản
  khác. BM25 xếp chunk này cao vì trùng cụm "xử lý", "sinh viên", "vi phạm", và RRF cho nó
  đủ điểm để chen lên. Đây đúng là nhiễu từ vựng mà nhóm đã dự đoán ở phase retrieval.
- **Faithfulness (−0.0357)** đến từ đúng một case: *"Bài thi được lưu trữ bao lâu?"* rơi từ
  1.000 xuống 0.500. Chỉ 1/14 case nên độ tin cậy thấp.
- **Answer relevance (−0.0081) nằm trong nhiễu đo, không nên diễn giải.** Bằng chứng: ở case
  *"Tài liệu học tập được số hóa... gọi là gì?"*, hai config sinh ra **câu trả lời giống hệt
  nhau từng ký tự** (`"Học liệu điện tử [Document 1, Điều 2]."`) nhưng được chấm 0.448 (A) và
  0.000 (B). `ResponseRelevancy` của RAGAS hoạt động bằng cách sinh ngược câu hỏi từ câu trả
  lời rồi so cosine; với câu trả lời quá ngắn, bước sinh ngược rất không ổn định.

**Vì sao RRF không giúp trên corpus này.** 6/13 tài liệu là quy chế của cùng một trường, dùng
chung vốn từ hành chính ("sinh viên", "học kỳ", "xử lý", "quy định"). BM25 xếp hạng theo trùng
từ nên thường xuyên kéo lên chunk đúng từ vựng nhưng sai chủ thể. RRF trung bình hóa thứ hạng
của hai danh sách, nên một danh sách nhiễu kéo tụt danh sách còn lại. RRF có lợi khi hai
retriever mắc **lỗi khác nhau**; ở đây BM25 mắc lỗi một cách có hệ thống trên chính loại câu
hỏi mà dense đã làm đúng.

**Trade-off latency/cost.** Đo trên 15 truy vấn, sau warm-up:

| Config | Trung bình | Trung vị | Max |
| ------ | ---------: | -------: | --: |
| A dense-only | 144.6 ms | 123.7 ms | 351.9 ms |
| B hybrid + RRF | 100.8 ms | 96.9 ms | 131.3 ms |

**Không được đọc bảng này là "B nhanh hơn".** `retrieve()` hiện gọi cả `semantic_search` lẫn
`lexical_search` ở cả hai config, chỉ khác bước hợp nhất, nên khối lượng tính toán gần như
giống nhau; chênh lệch 44 ms là do Config A chạy trước với cache lạnh. Về chi phí API thì hai
config **bằng nhau tuyệt đối**: embedding chạy cục bộ, BM25 và RRF chạy trong bộ nhớ, và mỗi
truy vấn chỉ gọi LLM đúng một lần ở tầng generation.

Kết luận thực dụng: Config B **không** mang lại lợi ích đo được trên corpus này, trong khi
làm tăng độ phức tạp và gây mất bằng chứng ở một case quan trọng. Nhóm chọn Config A làm cấu
hình mặc định, nhưng giữ nguyên đường hybrid trong code vì nó vẫn là yêu cầu của rubric và có
thể có lợi trên corpus đa dạng hơn về nguồn.

## Worst performers

|   # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| --: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------- | ---------- |
|   1 | Khi cán bộ phản biện đánh giá khóa luận tốt nghiệp dưới 5 điểm thì Khoa xử lý như thế nào? | B (và A cũng hỏng) | n/a (từ chối) | 0.000 | 0.000 | 0.950 | retrieval | Bất đối xứng viết tắt giữa câu hỏi và tài liệu |
|   2 | Sinh viên bị đuổi học trong những trường hợp nào? | B | 1.000 | 0.391 | **0.429** | 1.000 | retrieval | BM25 kéo nhầm chunk từ văn bản khác, RRF đẩy chunk đúng ra khỏi top-5 |
|   3 | Tài liệu học tập được số hóa dùng cho dạy học trực tuyến được gọi là gì? | B | 1.000 | **0.000** | 1.000 | 0.867 | generation | Câu trả lời quá cộc, không tự đứng vững ngoài ngữ cảnh câu hỏi |

### Case 1 — hỏng nặng nhất, cả hai config đều trượt

Cả 5 chunk lấy về đều từ **790/QĐ-ĐHCNTT** (Điều 31, Điều 32 về thực tập và chấm khóa luận),
trong khi câu trả lời nằm ở **159/QĐ-ĐHCNTT** Điều 10. `context_recall = 0.000`. Tầng
generation xử lý đúng: nhận ra context không chứa câu trả lời và từ chối thay vì bịa — nên
đây là lỗi retrieval thuần túy, không phải lỗi generation.

Nguyên nhân gốc đo được: **văn bản 159 gần như chỉ dùng viết tắt**.

| Cụm từ | Số lần trong 159 |
| ------ | ---------------: |
| `KLTN` | 113 |
| `khóa luận tốt nghiệp` | 11 |
| `CBPB` | 25 |
| `cán bộ phản biện` | 2 |

Câu hỏi của người dùng viết đầy đủ ("khóa luận tốt nghiệp", "cán bộ phản biện"), còn tài liệu
chứa câu trả lời lại viết tắt. Văn bản 790 thì viết đầy đủ, nên nó thắng ở cả dense lẫn BM25
dù không chứa quy định cần tìm. Bản mở rộng của các viết tắt chỉ xuất hiện đúng một lần, trong
Điều 2 (bảng thuật ngữ) — mà Điều 2 lại nằm ở chunk khác, nên không chunk nào của 159 vừa chứa
quy định vừa chứa dạng đầy đủ của từ khóa.

Case *"Mỗi năm Trường tổ chức bao nhiêu đợt bảo vệ khóa luận tốt nghiệp?"* đạt 0.882 **nhờ may
mắn**: văn bản 790 Điều 31 tình cờ cũng ghi "Hằng năm có 2 đợt bảo vệ khóa luận tốt nghiệp",
nên hệ thống trả lời đúng từ văn bản sai. Nếu hai văn bản mâu thuẫn nhau thì case này đã sai.

### Case 2 — RRF làm mất bằng chứng

Đã phân tích ở mục A/B comparison. Điểm đáng lưu ý: faithfulness vẫn 1.000 và precision vẫn
1.000, nghĩa là **nhìn vào ba metric kia sẽ không thấy gì bất thường**. Chỉ có recall lộ ra
việc mất bằng chứng. Đây là ví dụ cho thấy vì sao không được kết luận từ điểm trung bình.

### Case 3 — câu trả lời quá cộc

Câu trả lời là `"Học liệu điện tử [Document 1, Điều 2]."`. Về nội dung thì đúng hoàn toàn
(faithfulness 1.000, recall 1.000), nhưng `ResponseRelevancy` chấm 0.000 vì không sinh ngược
được câu hỏi hợp lý từ ba chữ. Nguyên nhân từ `SYSTEM_PROMPT`: nhóm viết "Không suy đoán, không
trả lời một phần, không xin lỗi dài dòng" để chống ảo giác, và mô hình hiểu thành phải trả lời
càng ngắn càng tốt. Đây là hệ quả không lường trước của một chỉ dẫn viết vì mục đích khác.

Lưu ý phương pháp: chính case này cho thấy `ResponseRelevancy` không ổn định — cùng một câu trả
lời được chấm 0.448 ở config A và 0.000 ở config B.

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
| 1 | Mở rộng viết tắt khi chunk: đọc bảng thuật ngữ (Điều 2 của mỗi văn bản), rồi chèn dạng đầy đủ vào chunk, ví dụ `KLTN (khóa luận tốt nghiệp)`. Cài đặt trong `chunk_documents()` của `src/task4_chunking_indexing.py`. | Case 1: 159 dùng `KLTN` 113 lần so với 11 lần viết đầy đủ, `CBPB` 25 lần so với 2 lần. Cả 5 chunk lấy về đều từ văn bản sai, `context_recall = 0.000`. | Case 1 từ recall 0.000 lên gần 1.000; các câu hỏi khác về KLTN đang đúng-nhờ-may-mắn sẽ lấy đúng văn bản nguồn. Ảnh hưởng chủ yếu tới nhóm `confusable` (recall hiện 0.800, thấp nhất trong ba nhóm). | `python -m src.task4_chunking_indexing` rồi `python -m src.run_evaluation`; so cột `chunk_ids` của case 1 trong `raw_results.json` — phải xuất hiện `legal/159-...::chunk-*`. Kiểm tra `context_recall` của nhóm `confusable` tăng. |
| 2 | ~~Sửa `SYSTEM_PROMPT` yêu cầu câu trả lời tự đứng vững, nhắc lại chủ thể của câu hỏi.~~ **Đã thử và bác bỏ bằng số đo — xem mục *Xác minh recommendation #2* bên dưới.** Hướng thay thế: chỉ bổ sung quy tắc xử lý câu nêu ý định, không đụng tới độ dài câu trả lời. | Case 3: câu trả lời `"Học liệu điện tử [Document 1, Điều 2]."` đúng nội dung nhưng relevance 0.000. Answer relevance trung bình chỉ 0.44 trên cả 15 case ở cả hai config. | Giả thuyết ban đầu: answer relevance tăng, faithfulness không đổi. **Thực tế cả hai đều giảm.** | Đã chạy lại `python -m src.run_evaluation` với cùng golden dataset và evaluator. Kết quả ghi ở mục dưới. |
| 3 | Bỏ nhánh hybrid khỏi đường mặc định: để `use_reranking=False` làm mặc định của `retrieve()`, giữ RRF như tùy chọn. Đồng thời bỏ qua `lexical_search()` khi `use_reranking=False` để không trả chi phí BM25 vô ích. | Config B thua trên cả 4 metric (average −0.0217). Case 2 cho thấy RRF đẩy `790::chunk-57` ra khỏi top-5 và thay bằng `1139::chunk-75` từ văn bản không liên quan. Đo latency cho thấy Config A hiện vẫn chạy BM25 dù không dùng kết quả. | Average trở về mức của Config A; latency Config A giảm vì bỏ được một lần quét BM25 trên 396 chunk. | Đặt lại mặc định rồi chạy `python -m src.run_evaluation`; kiểm tra bảng tổng hợp khớp cột Config A hiện tại. Đo lại latency bằng script cũ, thứ tự A/B đảo ngược để loại ảnh hưởng cache lạnh. |

Ghi chú về ưu tiên: đề xuất 1 và 2 tấn công hai tầng khác nhau (retrieval và generation) nên có
thể làm song song và đo tách biệt. Đề xuất 3 chỉ nên thực hiện **sau** đề xuất 1, vì việc mở
rộng viết tắt có thể làm BM25 hữu ích trở lại — khi đó kết luận A thắng B cần được đo lại.

## Xác minh recommendation #2 — kết quả âm tính

Nhóm đã thực hiện đúng quy trình "đề xuất → đo → kết luận theo số liệu" cho
recommendation #2. Kết quả **bác bỏ** đề xuất, và nhóm giữ lại toàn bộ quá trình này
thay vì lặng lẽ xóa đi.

### Thay đổi đã thử (prompt v2)

Thêm 4 quy tắc vào `SYSTEM_PROMPT` và bỏ vế "không trả lời một phần":

1. Câu trả lời phải tự đứng vững, nhắc lại chủ thể của câu hỏi.
2. Liệt kê đầy đủ mọi trường hợp/điều kiện có trong context.
3. Trả lời một phần và nói rõ phần nào thiếu, thay vì từ chối hoàn toàn.
4. Hiểu câu nêu ý định (ví dụ "tôi muốn đăng ký khóa luận tốt nghiệp") như yêu cầu
   trình bày quy định liên quan.

### Kết quả đo

Cùng 15 golden case, cùng evaluator, cùng corpus, cùng `top_k`. Chỉ prompt thay đổi.

| Metric | v1 — Config A | v2 — Config A | Δ | v1 — Config B | v2 — Config B | Δ |
| ------ | ------------: | ------------: | ------: | ------------: | ------------: | ------: |
| Faithfulness | 1.0000 | 0.8889 | **−0.1111** | 0.9643 | 0.9167 | −0.0476 |
| Answer relevance | 0.4426 | 0.4072 | **−0.0354** | 0.4345 | 0.3915 | −0.0430 |
| Context recall | 0.9238 | 0.9238 | 0.0000 | 0.8952 | 0.8952 | 0.0000 |
| Context precision | 0.9047 | 0.9192 | +0.0145 | 0.8903 | 0.8689 | −0.0214 |

Context recall không đổi ở cả hai config — đúng như kỳ vọng, vì prompt không tác động
tới tầng retrieval. Điều này xác nhận thí nghiệm cô lập đúng biến.

### Vì sao thất bại — và đây mới là phần đáng ghi nhận

Faithfulness tụt **không phải vì mô hình bịa**. Đối chiếu từng case cho thấy nội dung
vẫn chính xác, chỉ là câu trả lời dài ra:

| | Câu trả lời | Faithfulness |
| --- | --- | ---: |
| v1 | "Sinh viên được nghỉ học tạm thời tối đa hai học kỳ chính liên tiếp [Document 1, Điều 17]." | 1.000 |
| v2 | "...tối đa là hai học kỳ chính liên tiếp, **theo quy định tại Điều 17 của Quy chế đào tạo theo học chế tín chỉ cho hệ đại học chính quy**..." | 0.500 |

RAGAS Faithfulness tách câu trả lời thành các mệnh đề rồi kiểm từng mệnh đề với
context. Mệnh đề "theo quy định tại Điều 17 của Quy chế đào tạo..." là một **khẳng
định về xuất xứ**, không phải nội dung nằm trong đoạn văn bản được cung cấp, nên bị
tính là không kiểm chứng được. Quy tắc "nhắc lại chủ thể" đã đẩy tên văn bản từ nhãn
`[Document N]` vào văn xuôi.

Quy tắc đó cũng phá luôn chính metric nó nhắm tới:

| | Câu trả lời | Answer relevance |
| --- | --- | ---: |
| v1 | "Một tín chỉ học tập được quy định bằng 15 tiết học lý thuyết" | 0.762 |
| v2 | "**Theo Quy chế đào tạo theo học chế tín chỉ của Trường Đại học Công nghệ Thông tin**, một tín chỉ học tập được quy định bằng 15 tiết học lý thuyết" | 0.267 |

`ResponseRelevancy` sinh ngược câu hỏi từ câu trả lời rồi so cosine với câu hỏi gốc.
Tiền tố tên văn bản làm bước sinh ngược lệch hẳn khỏi câu hỏi ban đầu.

Ngoài ra, khi quan sát thủ công, prompt v2 còn khiến mô hình gộp cả context ở rìa vào
câu trả lời: với câu hỏi về điều kiện làm khóa luận, nó thêm yêu cầu chứng chỉ TOEIC
lấy từ văn bản 956 (chunk nhiễu do BM25 kéo lên), trong khi Điều 31 của 790 không hề
nhắc tới ngoại ngữ. Hai loại yêu cầu khác nhau bị trộn làm một. Điều này cho thấy
chunk nhiễu vốn vô hại khi prompt nghiêm lại trở thành nguồn suy diễn khi prompt nới —
một lý do nữa ủng hộ recommendation #3.

### Quyết định

**Quay lại prompt v1**, đang là bản triển khai trong `src/task10_generation.py`.
`raw_results.json` chứa kết quả của v1, khớp với cấu hình đang chạy;
`raw_results_prompt_v2_experiment.json` giữ lại kết quả v2 để đối chiếu.

Lỗi mà v2 sửa được là có thật: câu nêu ý định "tôi muốn đăng ký khóa luận tốt nghiệp"
bị từ chối sai ở v1, còn ở v2 thì trả lời đầy đủ. Nhưng nhóm không đổi 0.11 điểm
faithfulness lấy một cải thiện về trải nghiệm chưa đo được. Hướng đi đúng cho lần sau
là chỉ thêm đúng quy tắc số 4 của v2 (hiểu câu nêu ý định), giữ nguyên mọi ràng buộc
còn lại về độ dài và cách trích dẫn, rồi đo lại.

**Bài học phương pháp:** một đề xuất nghe hợp lý ("câu trả lời nên đầy đủ và tự đứng
vững hơn") vẫn có thể làm xấu chính metric nó nhắm tới, vì cách metric được định nghĩa
chứ không phải vì chất lượng câu trả lời thực sự giảm. Đây là lý do rubric yêu cầu mỗi
recommendation phải kèm cách kiểm tra lại.

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| Không thực hiện | — | — | — | Nhóm không nộp bonus ở lần chạy này. Các hướng trong rubric (HyDE, reranker nâng cao, conversation memory, deploy online) đều chưa được cài đặt, nên theo yêu cầu "bonus chỉ được tính khi có demo hoặc kết quả đo kiểm chứng", nhóm không kê khai. |

Vectorless retriever ở Task 8 tuy là phần tự cài đặt ngoài starter nhưng đã được dùng làm
fallback trong pipeline chính, nên nhóm tính nó vào hạng mục *Retrieval pipeline và fallback*
chứ không kê vào bonus.
