from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    num_docs: int = 100
    llm_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    embed_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    data_dir: Path = Path("data")
    parquet_file: str = "legal_chunks.parquet"
    index_file: str = "legal_vectors.index"

    @property
    def parquet_path(self) -> Path:
        return self.data_dir / self.parquet_file

    @property
    def index_path(self) -> Path:
        return self.data_dir / self.index_file
