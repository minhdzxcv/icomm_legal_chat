from __future__ import annotations

import re
from typing import Dict, List

import pandas as pd


def split_legal_doc(text: str) -> List[Dict[str, str]]:
    """Split legal text by article markers like 'Dieu 1', preserving the header."""
    if not isinstance(text, str):
        return []

    parts = re.split(r"(\n\s*Dieu\s+\d+)", text, flags=re.IGNORECASE)
    chunks: List[Dict[str, str]] = []
    if not parts:
        return chunks

    intro = parts[0].strip()
    if intro:
        chunks.append({"text": intro, "article": "Phan mo dau"})

    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        full = f"{header} {content}".strip()
        if full:
            chunks.append({"text": full, "article": header})

    return chunks


def split_text_by_length(text: str, max_words: int = 500) -> List[str]:
    words = text.split()
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


def build_chunks_dataframe(df_merged: pd.DataFrame) -> pd.DataFrame:
    source_col = "content" if "content" in df_merged.columns else "full_text"
    rows = []

    for _, row in df_merged.iterrows():
        base_chunks = split_legal_doc(str(row[source_col]))
        for chunk in base_chunks:
            item = {
                "text": chunk["text"],
                "article": chunk["article"],
                "title": row.get("title", "Unknown"),
                "url": row.get("url", ""),
                "document_number": row.get("document_number", ""),
            }
            item["word_count"] = len(item["text"].split())
            rows.append(item)

    df_chunks = pd.DataFrame(rows)

    final_rows = []
    for _, row in df_chunks.iterrows():
        if row["word_count"] > 600:
            sub_chunks = split_text_by_length(row["text"], max_words=500)
            for idx, sub in enumerate(sub_chunks, start=1):
                item = row.to_dict()
                item["text"] = sub
                item["article"] = f"{row['article']} (Phan {idx})"
                item["word_count"] = len(sub.split())
                final_rows.append(item)
        else:
            final_rows.append(row.to_dict())

    return pd.DataFrame(final_rows)
