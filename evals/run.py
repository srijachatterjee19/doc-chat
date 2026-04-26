#!/usr/bin/env python3
"""
Evaluate the RAG pipeline using RAGAS metrics.

Metrics:
  faithfulness            - does the answer stick to the retrieved context?
  answer_relevancy        - does the answer address the question?
  context_precision       - are retrieved chunks relevant? (requires ground_truth)

Usage:
  python -m evals.run
  python -m evals.run --questions evals/questions.json --model llama3.2 --k 3
  python -m evals.run --output evals/results.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _check_deps():
    missing = []
    for pkg in ("ragas", "datasets"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


def _generate_answer(question: str, chunks: list[str], model: str) -> str:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOllama(model=model)
    context = "\n\n".join(f"[Chunk {i+1}]\n{c}" for i, c in enumerate(chunks))
    messages = [
        SystemMessage(content=(
            "You are a helpful assistant. Answer the question using only the "
            "provided context. If the context does not contain the answer, say so clearly."
        )),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
    ]
    return llm.invoke(messages).content.strip()


def _score(rows: list[dict], model: str) -> "pd.DataFrame":
    from ragas import evaluate
    from ragas.metrics import Faithfulness, AnswerRelevancy, LLMContextPrecisionWithoutReference
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_ollama import ChatOllama, OllamaEmbeddings

    llm = LangchainLLMWrapper(ChatOllama(model=model))
    emb = LangchainEmbeddingsWrapper(OllamaEmbeddings(model="nomic-embed-text"))

    has_ground_truth = all(r.get("ground_truth") for r in rows)

    metrics = [
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm, embeddings=emb),
    ]
    if has_ground_truth:
        metrics.append(LLMContextPrecisionWithoutReference(llm=llm))

    samples = [
        SingleTurnSample(
            user_input=r["question"],
            retrieved_contexts=r["chunks"],
            response=r["answer"],
            reference=r.get("ground_truth") or None,
        )
        for r in rows
    ]
    dataset = EvaluationDataset(samples=samples)
    result = evaluate(dataset=dataset, metrics=metrics)
    return result.to_pandas()


def _print_results(rows: list[dict], df) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    metric_cols = [c for c in df.columns if c not in ("user_input", "retrieved_contexts", "response", "reference")]

    # Per-question table
    tbl = Table(box=box.SIMPLE_HEAD, show_footer=True)
    tbl.add_column("#",  style="dim", width=3)
    tbl.add_column("Question", no_wrap=False, max_width=48)
    tbl.add_column("Answer (preview)", no_wrap=False, max_width=40)
    for m in metric_cols:
        avg = df[m].mean()
        tbl.add_column(m.replace("_", " ").title(), justify="right", footer=f"[bold]{avg:.3f}[/bold]")

    for i, (row, (_, dfrow)) in enumerate(zip(rows, df.iterrows()), 1):
        cells = [
            str(i),
            row["question"][:80],
            row["answer"][:60] + ("…" if len(row["answer"]) > 60 else ""),
        ]
        for m in metric_cols:
            val = dfrow[m]
            if val != val:  # NaN
                cells.append("—")
            else:
                color = "green" if val >= 0.7 else ("yellow" if val >= 0.4 else "red")
                cells.append(f"[{color}]{val:.3f}[/{color}]")
        tbl.add_row(*cells)

    console.print()
    console.print(tbl)


def main():
    parser = argparse.ArgumentParser(description="Run RAGAS evals on the RAG pipeline")
    parser.add_argument("--questions", default="evals/questions.json")
    parser.add_argument("--model",     default="llama3.2",            help="Ollama model name")
    parser.add_argument("--k",         default=3, type=int,           help="Chunks to retrieve per question")
    parser.add_argument("--output",    default=None,                  help="Save JSON results to this path")
    args = parser.parse_args()

    _check_deps()

    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"Questions file not found: {questions_path}")
        sys.exit(1)

    test_cases = json.loads(questions_path.read_text())
    if not test_cases:
        print("No test cases in questions file.")
        sys.exit(1)

    from backend.src.vector_store import VectorStore
    vs = VectorStore()

    if vs.count() == 0:
        print("Vector store is empty — run ingest first.")
        sys.exit(1)

    print(f"Running {len(test_cases)} questions  |  model={args.model}  |  k={args.k}")

    rows = []
    for i, tc in enumerate(test_cases, 1):
        q = tc["question"]
        print(f"  [{i}/{len(test_cases)}] {q[:70]}")
        chunks = vs.similarity_search(q, k=args.k)
        answer = _generate_answer(q, chunks, args.model)
        rows.append({
            "question":     q,
            "ground_truth": tc.get("ground_truth", ""),
            "chunks":       chunks,
            "answer":       answer,
        })

    print("\nScoring with RAGAS…")
    df = _score(rows, args.model)
    _print_results(rows, df)

    if args.output:
        metric_cols = [c for c in df.columns if c not in ("user_input", "retrieved_contexts", "response", "reference")]
        out = {
            "summary": {m: round(float(df[m].mean()), 4) for m in metric_cols},
            "results": [
                {
                    "question": r["question"],
                    "answer":   r["answer"],
                    **{m: round(float(dfrow[m]), 4) for m in metric_cols if dfrow[m] == dfrow[m]},
                }
                for r, (_, dfrow) in zip(rows, df.iterrows())
            ],
        }
        Path(args.output).write_text(json.dumps(out, indent=2))
        print(f"Results saved → {args.output}")


if __name__ == "__main__":
    main()
