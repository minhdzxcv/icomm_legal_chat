from __future__ import annotations

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer


class HybridRetriever:
    def __init__(
        self,
        df_chunks: pd.DataFrame,
        index,
        embed_model_name: str,
        device: str = "cpu",
        rerank_model_name: str | None = None,
    ):
        self.df_chunks = df_chunks.reset_index(drop=True)
        self.index = index
        self.embed_model = SentenceTransformer(embed_model_name, device=device)
        self.reranker = CrossEncoder(rerank_model_name, device=device) if rerank_model_name else None
        self._rebuild_search_index()

    def _rebuild_search_index(self) -> None:
        self.df_chunks["search_text"] = (
            self.df_chunks["title"].fillna("")
            + " "
            + self.df_chunks["article"].fillna("")
            + " "
            + self.df_chunks["text"].fillna("")
        )
        tokenized = [doc.lower().split() for doc in self.df_chunks["search_text"].tolist()]
        self.bm25 = BM25Okapi(tokenized)

    def add_documents(self, new_docs: pd.DataFrame) -> int:
        if new_docs.empty:
            return 0

        required_cols = {"text", "article", "title", "url"}
        missing = required_cols - set(new_docs.columns)
        if missing:
            raise ValueError(f"Missing required columns in new documents: {missing}")

        clean_docs = new_docs.copy().reset_index(drop=True)
        clean_docs["word_count"] = clean_docs["text"].fillna("").astype(str).apply(lambda x: len(x.split()))
        new_vectors = self.embed_model.encode(clean_docs["text"].astype(str).tolist()).astype("float32")
        self.index.add(new_vectors)

        self.df_chunks = pd.concat([self.df_chunks, clean_docs], ignore_index=True)
        self._rebuild_search_index()
        return len(clean_docs)

    def search(self, query: str, k: int = 5, alpha: float = 0.5) -> pd.DataFrame:
        q_vec = self.embed_model.encode([query]).astype("float32")
        _, vec_indices = self.index.search(q_vec, max(k * 3, 10))
        vec_list = vec_indices[0]

        bm25_scores = self.bm25.get_scores(query.lower().split())
        bm25_indices = np.argsort(bm25_scores)[::-1][: max(k * 3, 10)]

        candidates = set(vec_list.tolist()) | set(bm25_indices.tolist())
        scores = {}

        for idx in candidates:
            v_pos = np.where(vec_list == idx)[0]
            v_score = 1 / (v_pos[0] + 60) if len(v_pos) else 0.0

            b_pos = np.where(bm25_indices == idx)[0]
            b_score = 1 / (b_pos[0] + 60) if len(b_pos) else 0.0

            scores[idx] = alpha * v_score + (1 - alpha) * b_score

        top_idx = sorted(scores, key=scores.get, reverse=True)[:k]
        result = self.df_chunks.iloc[top_idx].copy()
        result["hybrid_score"] = [scores[i] for i in top_idx]
        return result.reset_index(drop=True)

    def search_with_rerank(
        self,
        query: str,
        retrieve_k: int,
        rerank_top_n: int,
        alpha: float = 0.5,
    ) -> pd.DataFrame:
        import time
        t0 = time.time()
        docs = self.search(query, k=retrieve_k, alpha=alpha)
        t_search = time.time() - t0
        print(f"[PERF] Vector+BM25 Search retrieved {len(docs)} documents in {t_search:.3f}s")

        if docs.empty:
            return docs

        if not self.reranker:
            return docs.head(rerank_top_n).reset_index(drop=True)

        t1 = time.time()
        pairs = [(query, str(text)) for text in docs["text"].tolist()]
        rerank_scores = self.reranker.predict(pairs)
        docs = docs.copy()
        docs["rerank_score"] = rerank_scores
        docs = docs.sort_values(by="rerank_score", ascending=False).head(rerank_top_n)
        t_rerank = time.time() - t1
        
        print(f"[PERF] Reranking {len(pairs)} pairs took {t_rerank:.3f}s")
        if not docs.empty:
            print("[PERF] Reranked Top Scores:")
            # Use enumerate to get 1-based rank indexing safely
            for idx, (_, row) in enumerate(docs.head(5).iterrows(), start=1):
                print(f"[PERF]   Rank {idx}: Score={row['rerank_score']:.3f} | {row['title'][:30]}... - {row['article']}")
            
        return docs.reset_index(drop=True)
