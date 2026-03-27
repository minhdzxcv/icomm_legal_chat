from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import torch
import fitz
import docx

from .chunking import build_chunks_dataframe
from .conflict import ConflictAnalyzer
from .config import AppConfig
from .data_loader import load_legal_dataset
from .generation import LegalGenerator
from .intent_classifier import intent_classifier
from .indexing import (
    build_faiss_index,
    create_embeddings,
    find_existing_artifacts,
    load_artifacts,
    save_artifacts,
)
from .retrieval import HybridRetriever


@dataclass
class ChatHistory:
    max_len: int = 3
    turns: list[dict] = field(default_factory=list)

    def add(self, user_q: str, bot_a: str) -> None:
        self.turns.append({"user": user_q, "bot": bot_a})
        if len(self.turns) > self.max_len:
            self.turns.pop(0)

    def context(self) -> str:
        return "\n".join([f"User: {t['user']}\nBot: {t['bot']}" for t in self.turns])


class LegalRAGChatbot:
    def __init__(self, config: AppConfig):
        self.config = config
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.history = ChatHistory(max_len=3)

        self.retriever: HybridRetriever | None = None
        self.generator: LegalGenerator | None = None
        self.conflict_analyzer: ConflictAnalyzer | None = None

    @staticmethod
    def _extract_text_from_file(file_path: str | Path) -> str:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            text_parts = []
            with fitz.open(str(path)) as pdf_doc:
                for page in pdf_doc:
                    text_parts.append(page.get_text())
            return "\n".join(text_parts)

        if suffix == ".docx":
            word_doc = docx.Document(str(path))
            return "\n".join([p.text for p in word_doc.paragraphs])

        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")

        raise ValueError("Unsupported file type. Use pdf, docx, txt, or md.")

    @staticmethod
    def _text_to_upload_chunks(text: str, title: str, url: str = "local-upload") -> pd.DataFrame:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        rows = []
        for idx, para in enumerate(paras, start=1):
            if len(para.split()) < 20:
                continue
            rows.append(
                {
                    "text": para,
                    "article": f"Doan {idx}",
                    "title": title,
                    "url": url,
                    "document_number": "uploaded",
                }
            )
        return pd.DataFrame(rows)

    def build_or_load(self, force_rebuild: bool = False) -> None:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)

        if not force_rebuild:
            artifact_pair = find_existing_artifacts(self.config.data_dir)
        else:
            artifact_pair = None

        if artifact_pair:
            parquet_path, index_path = artifact_pair
            df_chunks, index = load_artifacts(parquet_path, index_path)

            # If parquet/index do not align, fallback to rebuild for consistency.
            if index.ntotal != len(df_chunks):
                force_rebuild = True

        if force_rebuild or not artifact_pair:
            df_raw = load_legal_dataset(num_docs=self.config.num_docs)
            df_chunks = build_chunks_dataframe(df_raw)
            embeddings = create_embeddings(df_chunks, self.config.embed_model, self.device)
            index = build_faiss_index(embeddings, use_ivf=True, nlist=8)
            save_artifacts(df_chunks, index, str(self.config.parquet_path), str(self.config.index_path))

        self.retriever = HybridRetriever(
            df_chunks,
            index,
            self.config.embed_model,
            self.device,
            rerank_model_name=self.config.rerank_model,
        )
        self.generator = LegalGenerator(self.config.llm_model, self.device)
        self.conflict_analyzer = ConflictAnalyzer(self.retriever, self.generator)

    @staticmethod
    def _format_references(docs: pd.DataFrame, max_refs: int = 5) -> str:
        if docs.empty:
            return ""

        lines = ["", "Nguon tham khao:"]
        for idx, (_, row) in enumerate(docs.head(max_refs).iterrows(), start=1):
            ref_id = row.get("evidence_id", f"E{idx}")
            lines.append(f"[{ref_id}] {row['title']} - {row['article']}")
            lines.append(f"   {row['url']}")
        return "\n".join(lines)

    def _collect_related_chunks(self, anchor: pd.Series, question: str, limit: int = 2) -> pd.DataFrame:
        """Collect chunks related to top-1 chunk from the same legal document for extra grounding."""
        if not self.retriever:
            return pd.DataFrame(columns=["title", "article", "url", "text"])

        pool = self.retriever.df_chunks.copy()
        same_title = pool[pool["title"] == anchor["title"]]

        if same_title.empty:
            return pd.DataFrame(columns=["title", "article", "url", "text"])

        # Remove the exact top-1 chunk to avoid duplicated context.
        related = same_title[
            ~(
                (same_title["article"] == anchor["article"])
                & (same_title["text"] == anchor["text"])
            )
        ].copy()

        if related.empty:
            return pd.DataFrame(columns=["title", "article", "url", "text"])

        query_tokens = set(question.lower().split())

        def overlap_score(text: str) -> int:
            text_tokens = set(str(text).lower().split())
            return len(query_tokens.intersection(text_tokens))

        related["_overlap"] = related["text"].astype(str).apply(overlap_score)
        related = related.sort_values(by="_overlap", ascending=False).head(limit)
        return related[["title", "article", "url", "text"]].reset_index(drop=True)

    def ask(self, question: str, k: int = 3) -> dict:
        if not self.retriever or not self.generator:
            raise RuntimeError("Call build_or_load() before asking questions.")

        # Classify query intent
        intent = intent_classifier.classify(question)
        print(f"🔍 DEBUG: Question='{question}' | Intent={intent}")
        
        if intent == "general":
            # General question - answer directly without legal sources
            print(f"  ✓ General: No search needed")
            # Reset history to avoid influencing future questions with legal context
            self.history.turns.clear()
            
            prompt = (
                "<|im_start|>system\n"
                "Bạn là một trợ lý hữu ích và thân thiện. "
                "Trả lời ngắn gọn, tự nhiên và hữu ích cho người dùng.\n<|im_end|>\n"
                "<|im_start|>user\n"
                f"{question}<|im_end|>\n"
                "<|im_start|>assistant\n"
            )
            answer = self.generator.answer(question=question, context_blocks=[prompt], max_new_tokens=200)
            self.history.add(question, answer)
            
            return {
                "answer": answer,
                "sources": [],
                "intent": "general"
            }
        
        elif intent == "conflict_analysis":
            # Conflict analysis - automatically route to analyze_conflict
            print(f"  ✓ Conflict Analysis: Route to analyze_conflict()")
            return self.analyze_conflict(question, k=k)
        
        else:  # intent == "legal_qa"
            # Legal Q&A - search and provide sources
            print(f"  ✓ Legal Q&A: Searching documents...")
            docs = self.retriever.search_with_rerank(question, retrieve_k=5, rerank_top_n=1)
            print(f"     Found {len(docs)} reranked documents")

            if len(docs) == 0:
                answer = "Thong tin khong co trong du lieu." 
                self.history.add(question, answer)
                return {
                    "answer": answer,
                    "sources": [],
                    "intent": "legal_qa",
                }

            print(f"     Top result (reranked): {docs.iloc[0]['title'][:50]}")
            top1 = docs.iloc[[0]].copy()
            anchor_row = top1.iloc[0]
            
            # CHIẾN THUẬT ĂN ĐIỂM: GỌI HÀM BỔ SUNG NGỮ CẢNH XUNG QUANH
            related_docs = self._collect_related_chunks(anchor_row, question, limit=2)
            
            # Gộp Top 1 và các ngữ cảnh vệ tinh xung quanh lại
            context_docs = pd.concat([top1, related_docs], ignore_index=True).drop_duplicates(subset=["text"])
            context_docs = context_docs.reset_index(drop=True)
            context_docs["evidence_id"] = [f"E{i+1}" for i in range(len(context_docs))]

            # Build nhiều block thay vì 1 block
            context_blocks = []
            for i, row in context_docs.iterrows():
                label = "[TOP1-CHUNG_CU_CHINH]" if i == 0 else "[CHUNG_CU_BO_TRO]"
                context_blocks.append(
                    f"[{row['evidence_id']}] {label}\n"
                    f"Van ban: {row['title']}\n"
                    f"Dieu/khoan: {row['article']}\n"
                    f"Noi dung: {row['text']}\n"
                    f"Link: {row['url']}"
                )

            memory = self.history.context()
            
            # Thay đổi Prompt một chút để LLM tổng hợp nhiều Chunk liên quan
            qa_instruction = (
                "QUY TAC TRA LOI:\n"
                "1) CHUNG CU CHINH bat buoc la [E1]. Cac chung cu [E2], [E3] mang tinh bo tro tinh huong.\n"
                "2) Phai tong hop tu DUY NHAT cac chung cu duoc cung cap de sinh cau tra loi hoan chinh.\n"
                "3) Khong duoc tra loi ra ngoai noi dung cac chung cu tren.\n"
                "4) Tu dong loai bo prefix [E1], [E2] trong cau tra loi cuoi cung ma hay chi ra ten Dieu Khoan."
            )
            
            if memory:
                full_question = f"{qa_instruction}\n\nLich su hoi dap:\n{memory}\n\nCau hoi moi:\n{question}"
            else:
                full_question = f"{qa_instruction}\n\nCau hoi:\n{question}"

            # Cho LLM tạo câu trả lời
            answer = self.generator.answer(full_question, context_blocks, max_new_tokens=400)
            
            # Xóa các định dạng [E] nếu còn sót để văn phong đẹp nhất
            for i, row in context_docs.iterrows():
                answer = answer.replace(f"[{row['evidence_id']}]", f"")
                answer = answer.replace(f"{row['evidence_id']}", f"{row['article']}")
                
            answer = f"{answer}{self._format_references(context_docs, max_refs=len(context_docs))}"
            self.history.add(question, answer)

            return {
                "answer": answer,
                "sources": context_docs[["evidence_id", "title", "article", "url", "text"]].to_dict(orient="records"),
                "intent": "legal_qa"
            }

    def analyze_conflict(self, topic_query: str, k: int = 5) -> dict:
        if not self.conflict_analyzer:
            raise RuntimeError("Call build_or_load() before conflict analysis.")

        report, docs, conflict_context = self.conflict_analyzer.analyze(topic_query, k=k)
        if not docs.empty:
            lines = [""]
            if conflict_context:
                lines.append(conflict_context)
                lines.append("")
            lines.append("Dan chung xung dot (Top 5):")
            for _, row in docs.head(5).iterrows():
                lines.append(f"- {row['title']} - {row['article']}")
                lines.append(f"   Noi dung xung dot: {row.get('conflict_text', row['text'])}")
                lines.append(f"   {row['url']}")
            report = f"{report}\n" + "\n".join(lines)

        self.history.add(topic_query, report)
        
        return {
            "answer": report,
            "sources": docs[
                [
                    "evidence_id",
                    "title",
                    "article",
                    "url",
                    "text",
                    "conflict_text",
                    "legal_type",
                    "legal_priority",
                    "rerank_score",
                ]
            ].to_dict(orient="records"),
            "conflict_context": conflict_context,
            "intent": "conflict_analysis"
        }

    def ingest_file(self, file_path: str, title: str | None = None) -> dict:
        if not self.retriever:
            raise RuntimeError("Call build_or_load() before ingesting documents.")

        file_text = self._extract_text_from_file(file_path)
        file_title = title or Path(file_path).name
        new_df = self._text_to_upload_chunks(file_text, title=file_title)
        added = self.retriever.add_documents(new_df)

        return {
            "added_chunks": added,
            "title": file_title,
        }
