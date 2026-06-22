from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    def zero_results() -> dict:
        per_question = [
            EvalResult(q, a, c, gt, 0.0, 0.0, 0.0, 0.0)
            for q, a, c, gt in zip(questions, answers, contexts, ground_truths)
        ]
        return {"faithfulness": 0.0, "answer_relevancy": 0.0,
                "context_precision": 0.0, "context_recall": 0.0,
                "per_question": per_question,
                "evaluation_status": "failed"}
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        df = result.to_pandas()
        per_question = [
            EvalResult(
                question=row["question"],
                answer=row["answer"],
                contexts=list(row["contexts"]),
                ground_truth=row["ground_truth"],
                faithfulness=float(row.get("faithfulness", 0.0) or 0.0),
                answer_relevancy=float(row.get("answer_relevancy", 0.0) or 0.0),
                context_precision=float(row.get("context_precision", 0.0) or 0.0),
                context_recall=float(row.get("context_recall", 0.0) or 0.0),
            )
            for _, row in df.iterrows()
        ]
        return {
            "faithfulness": sum(r.faithfulness for r in per_question) / max(len(per_question), 1),
            "answer_relevancy": sum(r.answer_relevancy for r in per_question) / max(len(per_question), 1),
            "context_precision": sum(r.context_precision for r in per_question) / max(len(per_question), 1),
            "context_recall": sum(r.context_recall for r in per_question) / max(len(per_question), 1),
            "per_question": per_question,
            "evaluation_status": "ok",
        }
    except Exception as e:
        print(f"  ⚠️  RAGAS evaluation failed: {e}")
        results = zero_results()
        results["evaluation_error"] = str(e)
        return results


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    diagnostic_tree = {
        "faithfulness": ("LLM hallucinating", "Tighten grounded prompt and lower temperature"),
        "context_recall": ("Missing relevant chunks", "Improve chunking, add BM25 coverage, or raise retrieval top_k"),
        "context_precision": ("Too many irrelevant chunks", "Add reranking, metadata filters, or reduce final context count"),
        "answer_relevancy": ("Answer does not match the question", "Improve answer prompt and preserve question intent"),
    }
    analyzed = []
    for result in eval_results:
        metrics = {
            "faithfulness": result.faithfulness,
            "answer_relevancy": result.answer_relevancy,
            "context_precision": result.context_precision,
            "context_recall": result.context_recall,
        }
        if all(score == 0.0 for score in metrics.values()):
            worst_metric = "evaluation_unavailable"
            diagnosis = "Evaluation did not produce metric scores"
            suggested_fix = "Install missing RAGAS dependencies and rerun with OPENAI_API_KEY"
        else:
            worst_metric = min(metrics, key=metrics.get)
            diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        analyzed.append({
            "question": result.question,
            "answer": result.answer,
            "ground_truth": result.ground_truth,
            "worst_metric": worst_metric,
            "score": round(sum(metrics.values()) / len(metrics), 4),
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })
    return sorted(analyzed, key=lambda item: item["score"])[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    report = {
        "aggregate": {
            k: results[k]
            for k in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
            if k in results
        },
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
        "evaluation_status": results.get("evaluation_status", "unknown"),
    }
    if "evaluation_error" in results:
        report["evaluation_error"] = results["evaluation_error"]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
