from __future__ import annotations

import pandas as pd
from datasets import load_dataset


def load_legal_dataset(num_docs: int = 100) -> pd.DataFrame:
    """Load and merge content + metadata from Hugging Face dataset."""
    ds_content = load_dataset(
        "th1nhng0/vietnamese-legal-documents",
        "content",
        split=f"data[:{num_docs}]",
    )
    ds_metadata = load_dataset(
        "th1nhng0/vietnamese-legal-documents",
        "metadata",
        split=f"data[:{num_docs}]",
    )

    df_merged = pd.concat([ds_metadata.to_pandas(), ds_content.to_pandas()], axis=1)
    df_merged = df_merged.loc[:, ~df_merged.columns.duplicated()]

    required_cols = {"title", "url"}
    missing = required_cols - set(df_merged.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if "content" not in df_merged.columns and "full_text" not in df_merged.columns:
        raise ValueError("Dataset must contain either 'content' or 'full_text'.")

    return df_merged
