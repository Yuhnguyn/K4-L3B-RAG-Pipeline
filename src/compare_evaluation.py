"""
So sánh hai lần chạy ``run_evaluation`` trên cùng golden dataset.

Dùng để kiểm chứng Recommendation #1 (mở rộng viết tắt): chạy baseline, bật
``expand_for_indexing``, chạy lại, rồi so từng metric và soi chunk_ids của case
KLTN/CBPB xem văn bản 159 đã lọt vào top-k chưa.

Chạy:
    python -m src.compare_evaluation \
        group_project/evaluation/raw_results.json \
        group_project/evaluation/raw_results_abbrev.json
"""

import argparse
import json
import statistics
from pathlib import Path


METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_recall",
    "context_precision",
]
CONFIGS = ("A_dense_only", "B_hybrid_rrf")
# Case "cán bộ phản biện đánh giá khóa luận dưới 5 điểm" trong golden dataset.
ABBREV_CASE_INDEX = 12


def mean(records: list[dict], metric: str) -> float:
    values = [
        record[metric]
        for record in records
        if isinstance(record.get(metric), (int, float))
        and record[metric] == record[metric]  # loại NaN
    ]
    return statistics.fmean(values) if values else float("nan")


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="raw_results.json trước khi thay đổi")
    parser.add_argument("candidate", help="raw_results.json sau khi thay đổi")
    parser.add_argument(
        "--case",
        type=int,
        default=ABBREV_CASE_INDEX,
        help="chỉ số case (1-based) cần soi chunk_ids",
    )
    args = parser.parse_args()

    baseline = load(args.baseline)
    candidate = load(args.candidate)

    print(f"{'config/metric':<30}{'baseline':>10}{'candidate':>11}{'delta':>10}")
    for config in CONFIGS:
        base_records = baseline["configs"].get(config, [])
        cand_records = candidate["configs"].get(config, [])
        for metric in METRICS:
            before, after = mean(base_records, metric), mean(cand_records, metric)
            print(
                f"{config + '/' + metric:<30}{before:>10.4f}"
                f"{after:>11.4f}{after - before:>+10.4f}"
            )

    index = args.case - 1
    for config in CONFIGS:
        base_records = baseline["configs"].get(config, [])
        cand_records = candidate["configs"].get(config, [])
        if index >= len(base_records) or index >= len(cand_records):
            continue
        print(f"\ncase {args.case} [{config}]: {base_records[index]['question']}")
        print(
            f"  context_recall      : "
            f"{base_records[index].get('context_recall')} -> "
            f"{cand_records[index].get('context_recall')}"
        )
        print(f"  chunk_ids baseline  : {base_records[index].get('chunk_ids', [])[:3]}")
        print(f"  chunk_ids candidate : {cand_records[index].get('chunk_ids', [])[:3]}")
        hit = any(
            "159-" in chunk_id
            for chunk_id in cand_records[index].get("chunk_ids", [])
        )
        print(f"  candidate lấy được văn bản 159? {hit}")


if __name__ == "__main__":
    main()
