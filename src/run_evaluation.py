"""
Đánh giá A/B bằng RAGAS.

Config A — dense-only:   retrieve(use_reranking=False)
Config B — hybrid + RRF: retrieve(use_reranking=True)

Chỉ retrieval strategy thay đổi. Golden dataset, generator, evaluator, prompt,
top_k và score_threshold giữ nguyên giữa hai config — nếu đổi nhiều biến cùng
lúc thì delta metric không cho biết RRF đóng góp gì.

Chạy:
    python -m src.run_evaluation

Kết quả thô ghi ra group_project/evaluation/raw_results.json để có thể kiểm tra
lại từng case mà không phải chạy lại toàn bộ (tốn API quota).
"""

import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .task10_generation import (
    SYSTEM_PROMPT,
    TOP_K,
    call_llm,
    format_context,
    reorder_for_llm,
    resolve_model,
)
from .task4_chunking_indexing import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL
from .task9_retrieval_pipeline import SCORE_THRESHOLD, retrieve


load_dotenv()

EVALUATION_DIR = Path(__file__).parent.parent / "group_project" / "evaluation"
GOLDEN_PATH = EVALUATION_DIR / "golden_dataset.json"
RAW_PATH = EVALUATION_DIR / "raw_results.json"

CONFIGS = {
    "A_dense_only": {"use_reranking": False},
    "B_hybrid_rrf": {"use_reranking": True},
}

# Tên cột do RAGAS trả về -> nhãn dùng trong báo cáo.
METRIC_COLUMNS = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "context_recall": "context_recall",
    "llm_context_precision_with_reference": "context_precision",
}
METRIC_NAMES = list(METRIC_COLUMNS.values())


def run_config(cases: list[dict], use_reranking: bool) -> list[dict]:
    """Chạy retrieval + generation cho mọi case của một config."""
    records = []
    for index, case in enumerate(cases, 1):
        query = case["question"]
        chunks = retrieve(query, top_k=TOP_K, use_reranking=use_reranking)

        if chunks:
            context = format_context(reorder_for_llm(chunks))
            try:
                answer = call_llm(SYSTEM_PROMPT, f"Context:\n{context}\n\nCâu hỏi: {query}")
            except Exception as error:
                answer = f"LOI_LLM: {type(error).__name__}"
        else:
            answer = "Tôi không thể xác minh thông tin này từ nguồn hiện có."

        records.append({
            "question": query,
            "question_type": case.get("question_type", ""),
            "answer": answer,
            "contexts": [chunk["content"] for chunk in chunks],
            "chunk_ids": [chunk["id"] for chunk in chunks],
            "retrieval_method": chunks[0]["retrieval_method"] if chunks else "none",
            "reference": case["expected_answer"],
            "expected_context": case["expected_context"],
        })
        print(f"  [{index:2}/{len(cases)}] {query[:58]}")
    return records


def score_with_ragas(records: list[dict]) -> dict:
    """Chấm 4 metric bằng RAGAS, dùng cùng evaluator cho cả hai config."""
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        Faithfulness,
        ResponseRelevancy,
        LLMContextRecall,
        LLMContextPrecisionWithReference,
    )

    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model=resolve_model(), temperature=0.0)
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model="text-embedding-3-small")
    )

    dataset = EvaluationDataset.from_list([
        {
            "user_input": record["question"],
            "response": record["answer"],
            "retrieved_contexts": record["contexts"] or [""],
            "reference": record["reference"],
        }
        for record in records
    ])

    result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextRecall(),
            LLMContextPrecisionWithReference(),
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
    )
    return result.to_pandas().to_dict(orient="list")


def main() -> None:
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    print(f"Golden dataset: {len(cases)} cases")
    print(f"Generator/Evaluator: {resolve_model()} | Embedding: {EMBEDDING_MODEL}")
    print(f"top_k={TOP_K} threshold={SCORE_THRESHOLD} chunk={CHUNK_SIZE}/{CHUNK_OVERLAP}\n")

    output = {
        "run_date": date.today().isoformat(),
        "generator_model": resolve_model(),
        "evaluator_model": resolve_model(),
        "embedding_model": EMBEDDING_MODEL,
        "top_k": TOP_K,
        "score_threshold": SCORE_THRESHOLD,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "configs": {},
    }

    for name, settings in CONFIGS.items():
        print(f"=== Config {name} ===")
        records = run_config(cases, **settings)
        print("  chấm điểm bằng RAGAS...")
        scores = score_with_ragas(records)
        for position, record in enumerate(records):
            for column, label in METRIC_COLUMNS.items():
                if column in scores:
                    record[label] = scores[column][position]
        output["configs"][name] = records
        print()

    RAW_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Kết quả thô -> {RAW_PATH}")

    print("\n=== TỔNG HỢP ===")
    print(f"{'Metric':<22}{'Config A':>10}{'Config B':>10}{'Delta B-A':>12}")
    for metric in METRIC_NAMES:
        values = {}
        for name in CONFIGS:
            scores = [
                record[metric] for record in output["configs"][name]
                if isinstance(record.get(metric), (int, float)) and record[metric] == record[metric]
            ]
            values[name] = sum(scores) / len(scores) if scores else float("nan")
        delta = values["B_hybrid_rrf"] - values["A_dense_only"]
        print(f"{metric:<22}{values['A_dense_only']:>10.4f}"
              f"{values['B_hybrid_rrf']:>10.4f}{delta:>+12.4f}")


if __name__ == "__main__":
    main()
