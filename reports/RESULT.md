# RAG evaluation results

Báo cáo đánh giá đầy đủ nằm ở một nguồn duy nhất:

**`group_project/evaluation/RESULT.md`**

Lý do gộp về một nơi: `tests/test_acceptance.py` đọc `group_project/evaluation/RESULT.md`,
còn `README.md` và `docs/STEP_BY_STEP.md` cũng trỏ về đó. Trước đây file này là bản sao
616 dòng của báo cáo, hai bản trôi lệch nhau (một bản ghi 396 chunk, một bản ghi 422).

Kết quả thô từng case: `group_project/evaluation/raw_results.json`.
Script tái lập: `python -m src.run_evaluation`.
