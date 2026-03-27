from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


@dataclass
class VectorArtifacts:
    embeddings: np.ndarray
    index: faiss.Index


def create_embeddings(df_chunks: pd.DataFrame, model_name: str, device: str) -> np.ndarray:
    model = SentenceTransformer(model_name, device=device)
    vectors = model.encode(df_chunks["text"].tolist(), show_progress_bar=True)
    return np.asarray(vectors, dtype="float32")


def build_faiss_index(embeddings: np.ndarray, use_ivf: bool = True, nlist: int = 8) -> faiss.Index:
    dim = embeddings.shape[1]

    if use_ivf and len(embeddings) > nlist:
        quantizer = faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_L2)
        index.train(embeddings)
        index.add(embeddings)
        index.nprobe = min(4, nlist)
        return index

    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index


def save_artifacts(df_chunks: pd.DataFrame, index: faiss.Index, parquet_path: str, index_path: str) -> None:
    df_chunks.to_parquet(parquet_path)
    faiss.write_index(index, index_path)


def load_artifacts(parquet_path: str, index_path: str) -> tuple[pd.DataFrame, faiss.Index]:
    df = pd.read_parquet(parquet_path)
    index = faiss.read_index(index_path)
    return df, index


def find_existing_artifacts(data_dir: str | Path) -> tuple[str, str] | None:
    """Find a usable parquet/index pair inside data directory."""
    base = Path(data_dir)
    default_parquet = base / "legal_chunks.parquet"
    default_index = base / "legal_vectors.index"

    if default_parquet.exists() and default_index.exists():
        return str(default_parquet), str(default_index)

    parquets = sorted(base.glob("*.parquet"))
    indices = sorted(base.glob("*.index"))
    if not parquets or not indices:
        return None

    # Prefer matching stems when possible, else first available pair.
    for p in parquets:
        for i in indices:
            if p.stem.replace("data", "vector") in i.stem or i.stem.replace("vector", "data") in p.stem:
                return str(p), str(i)

    return str(parquets[0]), str(indices[0])
