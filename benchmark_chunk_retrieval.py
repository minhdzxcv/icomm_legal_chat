from __future__ import annotations

import statistics
import time
from pathlib import Path

import pandas as pd

from src.legal_chatbot.chunking import build_chunks_dataframe
from src.legal_chatbot.config import AppConfig
from src.legal_chatbot.indexing import find_existing_artifacts, load_artifacts
from src.legal_chatbot.retrieval import HybridRetriever


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def to_ms(seconds: float) -> float:
    return seconds * 1000.0


def benchmark_chunking(df_chunks: pd.DataFrame, runs: int = 10) -> dict:
    # Reconstruct pseudo source docs from existing chunks to benchmark the chunk builder.
    source_col = "content"
    sample_docs = (
        df_chunks.groupby("title", as_index=False)
        .agg({"text": lambda s: "\n\n".join(s.astype(str).head(12)), "url": "first", "document_number": "first"})
        .rename(columns={"text": source_col})
        .head(50)
    )

    latencies = []
    chunk_counts = []
    for _ in range(runs):
        start = time.perf_counter()
        out_df = build_chunks_dataframe(sample_docs)
        end = time.perf_counter()
        latencies.append(end - start)
        chunk_counts.append(len(out_df))

    return {
        "runs": runs,
        "input_docs": len(sample_docs),
        "output_chunks_mean": statistics.mean(chunk_counts) if chunk_counts else 0,
        "avg_ms": to_ms(statistics.mean(latencies)),
        "min_ms": to_ms(min(latencies)),
        "max_ms": to_ms(max(latencies)),
        "p95_ms": to_ms(percentile(latencies, 95)),
    }


def benchmark_retrieval(df_chunks: pd.DataFrame, index, embed_model: str, runs: int = 30, k: int = 5) -> dict:
    retriever = HybridRetriever(df_chunks, index, embed_model_name=embed_model, device="cpu")
    queries = [
        "quy định về bảo hiểm xã hội",
        "mức xử phạt vi phạm giao thông",
        "điều kiện thành lập doanh nghiệp",
        "nghĩa vụ thuế của công ty",
        "so sánh quy định lao động và bảo hiểm",
    ]

    latencies = []
    result_sizes = []
    for i in range(runs):
        q = queries[i % len(queries)]
        start = time.perf_counter()
        result = retriever.search(q, k=k)
        end = time.perf_counter()
        latencies.append(end - start)
        result_sizes.append(len(result))

    return {
        "runs": runs,
        "k": k,
        "avg_result_size": statistics.mean(result_sizes) if result_sizes else 0,
        "avg_ms": to_ms(statistics.mean(latencies)),
        "min_ms": to_ms(min(latencies)),
        "max_ms": to_ms(max(latencies)),
        "p95_ms": to_ms(percentile(latencies, 95)),
        "qps_estimate": 1.0 / statistics.mean(latencies) if latencies else 0,
    }


def benchmark_retrieval_multi_k(df_chunks: pd.DataFrame, index, embed_model: str, runs: int = 30) -> list[dict]:
    results = []
    for k in (3, 5, 10, 20):
        results.append(benchmark_retrieval(df_chunks, index, embed_model=embed_model, runs=runs, k=k))
    return results


def demo_real_query(retriever: HybridRetriever, query: str, k: int = 5, runs: int = 20) -> dict:
    start = time.perf_counter()
    result = retriever.search(query, k=k)
    end = time.perf_counter()
    single_ms = to_ms(end - start)

    multi_latencies = []
    for _ in range(runs):
        t0 = time.perf_counter()
        _ = retriever.search(query, k=k)
        t1 = time.perf_counter()
        multi_latencies.append(t1 - t0)

    return {
        "query": query,
        "k": k,
        "single_ms": single_ms,
        "avg_ms": to_ms(statistics.mean(multi_latencies)),
        "min_ms": to_ms(min(multi_latencies)),
        "max_ms": to_ms(max(multi_latencies)),
        "p95_ms": to_ms(percentile(multi_latencies, 95)),
        "qps_estimate": 1.0 / statistics.mean(multi_latencies) if multi_latencies else 0,
        "result": result,
    }


def main() -> None:
    config = AppConfig()
    artifacts = find_existing_artifacts(config.data_dir)
    if not artifacts:
        raise RuntimeError(
            f"No artifacts found in {Path(config.data_dir).resolve()}. Run indexing/build_or_load first."
        )

    parquet_path, index_path = artifacts
    df_chunks, index = load_artifacts(parquet_path, index_path)

    if len(df_chunks) == 0:
        raise RuntimeError("Loaded chunk dataframe is empty.")

    print("=== Benchmark: Chunking and Retrieval ===")
    print(f"Artifacts: parquet={parquet_path}, index={index_path}")
    print(f"Total chunks loaded: {len(df_chunks)}")

    chunking = benchmark_chunking(df_chunks, runs=10)
    retrieval = benchmark_retrieval(df_chunks, index, embed_model=config.embed_model, runs=30, k=5)
    retrieval_multi_k = benchmark_retrieval_multi_k(df_chunks, index, embed_model=config.embed_model, runs=30)

    retriever = HybridRetriever(df_chunks, index, embed_model_name=config.embed_model, device="cpu")
    real_query_stats = demo_real_query(
        retriever=retriever,
        query="quy định xử phạt vi phạm hành chính về thuế hóa đơn",
        k=5,
        runs=20,
    )

    print("\n[Chunking]")
    print(f"Runs: {chunking['runs']} | Input docs: {chunking['input_docs']} | Mean output chunks: {chunking['output_chunks_mean']:.1f}")
    print(
        f"Latency (ms): avg={chunking['avg_ms']:.2f}, min={chunking['min_ms']:.2f}, "
        f"p95={chunking['p95_ms']:.2f}, max={chunking['max_ms']:.2f}"
    )

    print("\n[Retrieval]")
    print(f"Runs: {retrieval['runs']} | k={retrieval['k']} | Mean results: {retrieval['avg_result_size']:.1f}")
    print(
        f"Latency (ms): avg={retrieval['avg_ms']:.2f}, min={retrieval['min_ms']:.2f}, "
        f"p95={retrieval['p95_ms']:.2f}, max={retrieval['max_ms']:.2f}"
    )
    print(f"Estimated QPS: {retrieval['qps_estimate']:.2f}")

    print("\n[Retrieval by Top K]")
    for row in retrieval_multi_k:
        print(
            f"k={row['k']:>2} | avg={row['avg_ms']:.2f}ms | p95={row['p95_ms']:.2f}ms | "
            f"max={row['max_ms']:.2f}ms | qps~{row['qps_estimate']:.2f}"
        )

    print("\n[Real Query Demo]")
    print(f"Query: {real_query_stats['query']}")
    print(
        f"Latency (ms): one-shot={real_query_stats['single_ms']:.2f}, avg={real_query_stats['avg_ms']:.2f}, "
        f"min={real_query_stats['min_ms']:.2f}, p95={real_query_stats['p95_ms']:.2f}, max={real_query_stats['max_ms']:.2f}"
    )
    print(f"Estimated QPS: {real_query_stats['qps_estimate']:.2f}")
    print("Top retrieved chunks:")
    result_df = real_query_stats["result"]
    for i, (_, row) in enumerate(result_df.iterrows(), start=1):
        print(f"  {i}. {row['title']} | {row['article']} | score={row['hybrid_score']:.6f}")
        print(f"     URL: {row['url']}")


if __name__ == "__main__":
    main()
