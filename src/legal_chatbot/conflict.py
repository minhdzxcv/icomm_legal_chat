from __future__ import annotations

import re
from typing import Tuple

import pandas as pd

from .generation import LegalGenerator
from .legal_rank import detect_legal_type, legal_priority
from .retrieval import HybridRetriever


class ConflictAnalyzer:
    def __init__(self, retriever: HybridRetriever, generator: LegalGenerator):
        self.retriever = retriever
        self.generator = generator

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(str(text).lower().split())

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        union = a | b
        if not union:
            return 0.0
        return len(a & b) / len(union)

    def _select_diverse_top_docs(self, docs: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
        """Select top_n documents with rerank quality + diversity to surface potential conflicts."""
        if docs.empty:
            return docs

        working = docs.copy().reset_index(drop=True)
        selected_indices: list[int] = []
        token_cache = [self._tokenize(t) for t in working["text"].tolist()]

        for _ in range(min(top_n, len(working))):
            best_idx = None
            best_score = -1.0

            for idx in range(len(working)):
                if idx in selected_indices:
                    continue

                base_score = float(working.iloc[idx].get("rerank_score", 0.0))

                if not selected_indices:
                    mmr_score = base_score
                else:
                    max_sim = max(
                        self._jaccard(token_cache[idx], token_cache[s_idx]) for s_idx in selected_indices
                    )
                    # Encourage novelty so the final top-5 contains contrasting legal clauses.
                    mmr_score = 0.7 * base_score + 0.3 * (1 - max_sim)

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            if best_idx is None:
                break
            selected_indices.append(best_idx)

        selected = working.iloc[selected_indices].copy().reset_index(drop=True)
        return selected

    def _build_difference_hints(self, docs: pd.DataFrame) -> str:
        """Build concise pairwise differences to guide the LLM toward concrete conflict points."""
        if len(docs) < 2:
            return "- Chua du so nguon de so sanh cap cap."

        hints = []
        for i in range(len(docs)):
            text_i_tokens = self._tokenize(docs.iloc[i]["text"])
            for j in range(i + 1, len(docs)):
                text_j_tokens = self._tokenize(docs.iloc[j]["text"])
                sim = self._jaccard(text_i_tokens, text_j_tokens)
                if sim < 0.35:
                    hints.append(
                        f"- [E{i + 1}] va [E{j + 1}] co noi dung khac biet ro (do tuong dong token ~ {sim:.2f})."
                    )

        if not hints:
            return "- Cac nguon co muc do tuong dong cao, uu tien tim khac biet tinh huong ap dung."
        return "\n".join(hints[:10])

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[\.!?;:])\s+", str(text).strip())
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _is_noisy_sentence(sentence: str) -> bool:
        s = sentence.strip()
        if not s:
            return True
        if len(s) < 20:
            return True
        if re.fullmatch(r"[0-9\s\.,;:()\-\/]+", s):
            return True
        alnum_count = len(re.findall(r"[A-Za-z0-9À-ỹà-ỹ]", s))
        punct_count = len(re.findall(r"[\.,;:()\-\/]", s))
        if alnum_count > 0 and punct_count / alnum_count > 0.6:
            return True
        return False

    @staticmethod
    def _has_legal_signal(sentence: str) -> bool:
        s = sentence.lower()
        cues = [
            "phat",
            "tien phat",
            "muc",
            "tu",
            "den",
            "khong",
            "phai",
            "cam",
            "duoc",
            "thoi han",
            "ngay",
            "thang",
            "dieu",
            "khoan",
            "truong hop",
            "tron thue",
            "khai sai",
            "khac phuc hau qua",
            "phan tram",
            "lan so thue",
        ]
        has_number = bool(re.search(r"\d", s))
        return has_number or any(c in s for c in cues)

    def _extract_conflict_span(self, text: str, other_texts: list[str], max_sentences: int = 3) -> str:
        sentences = [s for s in self._split_sentences(text) if not self._is_noisy_sentence(s)]
        if not sentences:
            return str(text)

        other_tokens = self._tokenize(" ".join(other_texts)) if other_texts else set()
        scored: list[tuple[float, str]] = []

        for sentence in sentences:
            sent_tokens = self._tokenize(sentence)
            sim = self._jaccard(sent_tokens, other_tokens) if other_tokens else 0.0
            novelty = 1 - sim
            signal_bonus = 0.2 if self._has_legal_signal(sentence) else 0.0
            score = novelty + signal_bonus
            scored.append((score, sentence))

        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [sent for score, sent in scored if score >= 0.55][:max_sentences]

        if not picked:
            picked = [sent for _, sent in scored[:max_sentences]]

        return " ".join(picked).strip()

    def _build_conflict_context_summary(self, docs: pd.DataFrame, max_items: int = 5) -> str:
        if docs.empty:
            return ""

        lines = ["Tom tat context xung dot:"]
        for i, row in docs.head(max_items).iterrows():
            snippet = str(row.get("conflict_text", row.get("text", ""))).replace("\n", " ").strip()
            if len(snippet) > 160:
                snippet = snippet[:157] + "..."
            lines.append(f"- {row['article']}: {snippet}")
        return "\n".join(lines)

    @staticmethod
    def _decision_from_candidates(candidates: list[dict]) -> str:
        return "CO" if any(c.get("level") == "xung_dot" for c in candidates) else "KHONG"

    @staticmethod
    def _extract_money_values(text: str) -> list[int]:
        values: list[int] = []
        matches = re.findall(r"(\d[\d\.]*)\s*dong", str(text).lower())
        for raw in matches:
            num = raw.replace(".", "")
            if num.isdigit():
                values.append(int(num))
        return values

    @staticmethod
    def _extract_time_values(text: str) -> list[tuple[int, str]]:
        pairs: list[tuple[int, str]] = []
        for num, unit in re.findall(r"(\d+)\s*(nam|thang|ngay)", str(text).lower()):
            if num.isdigit():
                pairs.append((int(num), unit))
        return pairs

    @staticmethod
    def _detect_flags(text: str) -> set[str]:
        t = str(text).lower()
        flags = set()
        if "phat" in t or "tien phat" in t:
            flags.add("phat_tien")
        if "mien tien phat" in t or "mien phat" in t:
            flags.add("mien_phat")
        if "thoi hieu" in t:
            flags.add("thoi_hieu")
        if "tinh tiet giam nhe" in t or "tang nang" in t:
            flags.add("tinh_tiet")
        if "buoc" in t or "khac phuc" in t:
            flags.add("bien_phap")
        return flags

    @staticmethod
    def _topic_overlap_terms(text_a: str, text_b: str) -> list[str]:
        focus_terms = [
            "tron thue",
            "thue",
            "hoa don",
            "muc phat",
            "tien phat",
            "thoi hieu",
            "mien phat",
            "to chuc",
            "ca nhan",
            "khac phuc hau qua",
        ]
        a = str(text_a).lower()
        b = str(text_b).lower()
        return [term for term in focus_terms if term in a and term in b]

    def _build_conflict_candidates(self, docs: pd.DataFrame, max_pairs: int = 5) -> list[dict]:
        candidates: list[dict] = []
        if len(docs) < 2:
            return candidates

        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                e1 = f"E{i + 1}"
                e2 = f"E{j + 1}"
                t1 = str(docs.iloc[i].get("conflict_text", docs.iloc[i]["text"]))
                t2 = str(docs.iloc[j].get("conflict_text", docs.iloc[j]["text"]))
                f1 = self._detect_flags(t1)
                f2 = self._detect_flags(t2)
                common_topics = self._topic_overlap_terms(t1, t2)

                money1 = self._extract_money_values(t1)
                money2 = self._extract_money_values(t2)
                time1 = self._extract_time_values(t1)
                time2 = self._extract_time_values(t2)

                conflict_reason = None
                level = "khac_biet"

                if "mien_phat" in f1 and "phat_tien" in f2:
                    conflict_reason = "mot ben quy dinh mien phat, ben con lai quy dinh xu phat"
                    level = "xung_dot"
                elif "mien_phat" in f2 and "phat_tien" in f1:
                    conflict_reason = "mot ben quy dinh xu phat, ben con lai quy dinh mien phat"
                    level = "xung_dot"
                elif "thoi_hieu" in f1 and "thoi_hieu" in f2 and time1 and time2 and set(time1) != set(time2):
                    conflict_reason = "thoi hieu ap dung khac nhau"
                    level = "xung_dot"
                elif "phat_tien" in f1 and "phat_tien" in f2 and money1 and money2 and set(money1) != set(money2):
                    conflict_reason = "muc tien phat/tran phat khac nhau"
                elif common_topics:
                    conflict_reason = "khac biet ve cach ap dung tren cung nhom chu de"

                if not conflict_reason:
                    continue

                candidates.append(
                    {
                        "pair": f"[{e1}] vs [{e2}]",
                        "e1": e1,
                        "e2": e2,
                        "reason": conflict_reason,
                        "level": level,
                        "common_topics": common_topics,
                    }
                )

        candidates.sort(key=lambda x: (x["level"] != "xung_dot", -len(x["common_topics"])))

        if not candidates:
            # Always provide at least a few pair mappings so downstream report is actionable.
            for i in range(min(3, len(docs) - 1)):
                candidates.append(
                    {
                        "pair": f"[E{i + 1}] vs [E{i + 2}]",
                        "e1": f"E{i + 1}",
                        "e2": f"E{i + 2}",
                        "reason": "khac biet boi canh ap dung, can doi chieu them nguyen van",
                        "level": "khac_biet",
                        "common_topics": [],
                    }
                )

        return candidates[:max_pairs]

    @staticmethod
    def _format_candidates(candidates: list[dict]) -> str:
        if not candidates:
            return "- Khong tim thay cap co dau hieu xung dot ro rang, uu tien danh gia khac biet bo tro."
        lines = []
        for c in candidates:
            topics = ", ".join(c["common_topics"]) if c["common_topics"] else "(khong co tu khoa giao nhau ro rang)"
            lines.append(f"- {c['pair']} | muc_do={c['level']} | ly_do={c['reason']} | chu_de_giao_nhau={topics}")
        return "\n".join(lines)

    @staticmethod
    def _looks_like_template_output(answer: str) -> bool:
        a = str(answer).strip().lower()
        if not a:
            return True
        template_signals = [
            "dinh dang tra loi",
            "[e?]",
            "co xung dot / khong co xung dot",
        ]
        has_signal = any(s in a for s in template_signals)
        has_specific_ref = bool(re.search(r"\[e[1-5]\]", a))
        has_pair_mapping = bool(re.search(r"\[e[1-5]\]\s*vs\s*\[e[1-5]\]", a))
        generic_opening = "dua vao noi dung phap luat da cung cap" in a
        missing_decision = ("co xung dot" not in a) and ("khong xung dot" not in a)
        return (
            (has_signal and not has_pair_mapping)
            or (generic_opening and not has_pair_mapping)
            or (has_specific_ref and not has_pair_mapping)
            or missing_decision
        )

    def _build_fallback_report(self, topic_query: str, docs: pd.DataFrame, candidates: list[dict], decision: str) -> str:
        lines = [f"Ket luan: {'CO XUNG DOT' if decision == 'CO' else 'KHONG XUNG DOT'}."]
        lines.append(f"Chu de: {topic_query}")
        real_conflicts = [c for c in candidates if c["level"] == "xung_dot"]

        if real_conflicts:
            lines.append("Ly do chinh:")
            for c in real_conflicts[:3]:
                lines.append(f"- {c['pair']}: {c['reason']}.")
        else:
            lines.append("Ly do chinh:")
            lines.append("- Chua thay quy tac trai nguoc truc tiep; chu yeu la khac biet bo tro.")

        return "\n".join(lines)

    def _extract_expansion_terms(self, texts: list[str], max_terms: int = 10) -> list[str]:
        stopwords = {
            "va",
            "la",
            "co",
            "khong",
            "cho",
            "cua",
            "trong",
            "theo",
            "mot",
            "nhung",
            "khi",
            "neu",
            "duoc",
            "toi",
            "da",
            "tu",
            "den",
            "voi",
            "nguoi",
            "to",
            "chuc",
        }
        freq: dict[str, int] = {}
        for text in texts:
            for token in re.findall(r"[a-zA-Z0-9_]{3,}", str(text).lower()):
                if token in stopwords:
                    continue
                freq[token] = freq.get(token, 0) + 1

        ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [token for token, _ in ranked[:max_terms]]

    def analyze(self, topic_query: str, k: int = 5) -> Tuple[str, pd.DataFrame, str]:
        retrieve_k = 10
        final_top_n = 5

        docs = self.retriever.search_with_rerank(
            topic_query,
            retrieve_k=retrieve_k,
            rerank_top_n=retrieve_k,
        ).copy()

        if docs.empty:
            return "Thong tin khong co trong du lieu.", docs

        docs = self._select_diverse_top_docs(docs, top_n=final_top_n)
        docs["legal_type"] = docs["title"].apply(detect_legal_type)
        docs["legal_priority"] = docs["title"].apply(legal_priority)
        docs = docs.sort_values(by=["legal_priority", "rerank_score"], ascending=[True, False]).reset_index(drop=True)
        docs["evidence_id"] = [f"E{i + 1}" for i in range(len(docs))]

        all_texts = docs["text"].astype(str).tolist()
        conflict_texts = []
        for idx, text in enumerate(all_texts):
            other_texts = [t for j, t in enumerate(all_texts) if j != idx]
            conflict_texts.append(self._extract_conflict_span(text, other_texts))
        docs["conflict_text"] = conflict_texts

        expansion_terms = self._extract_expansion_terms(conflict_texts, max_terms=8)
        anchor_query = f"{topic_query} {' '.join(expansion_terms)}".strip()
        anchor_docs = self.retriever.search_with_rerank(anchor_query, retrieve_k=5, rerank_top_n=1)

        if not anchor_docs.empty:
            anchor_row = anchor_docs.iloc[0]
            anchor_block = (
                "=== NGU CANH NEO [A1] ===\n"
                f"Van ban: {anchor_row['title']}\n"
                f"Dieu/khoan: {anchor_row['article']}\n"
                f"Noi dung neo: {anchor_row['text']}\n"
            )
        else:
            anchor_block = (
                "=== NGU CANH NEO [A1] ===\n"
                f"Noi dung neo: {docs.iloc[0]['conflict_text']}\n"
            )

        # Format context blocks for conflict-focused generation.
        context_blocks = [anchor_block]
        for i, row in docs.iterrows():
            context_blocks.append(
                f"=== NGUON [E{i + 1}] | DIEU {i + 1}: {row['article']} ===\n"
                f"Van ban: {row['title']}\n"
                f"Loai: {row['legal_type']} | Uu tien: {row['legal_priority']}\n"
                f"NOI DUNG XUNG DOT:\n{row['conflict_text']}\n"
            )

        difference_hints = self._build_difference_hints(docs)
        candidates = self._build_conflict_candidates(docs, max_pairs=5)
        candidate_block = self._format_candidates(candidates)
        decision = self._decision_from_candidates(candidates)
        question = (
            "PHAN TICH XUNG DOT PHAP LY NGAN GON, TAP TRUNG CAP DOI CHIEU, VAN PHONG TU NHIEN:\n\n"
            "YEU CAU BAT BUOC (NGUYEN TAC NGANH LUAT):\n"
            "1) Nguyen tac Thu bac (Lex Superior): Bo Luat/Luat > Nghi Dinh > Thong Tu. Van ban cap cao phu quyet van ban cap thap. Neu co xung dot, bat buoc uu tien ap dung Van ban cap cao hon.\n"
            "2) Nguyen tac Thoi gian (Lex Posterior): Giua 2 van ban ngang cap, van ban ban hanh hoac co hieu luc sau se thay the van ban truoc do.\n"
            "3) Chi ket luan 'XUNG DOT THUC SU' khi hai van ban dua ra quy tac, muc phat, hay che tai trai ngoe hoan toan cho cung mot tinh huong.\n"
            "4) Neu 1 van ban chi huong dan chi tiet hon, hoac mo rong them tinh huong phat sinh cho van ban kia thi do la 'BO SUNG', TUYET DOI KHONG PHAI xung dot.\n"
            "5) Chi su dung chinh xac noi dung trong cac chung cu [E1]...[E5] duoc cung cap de chung minh, khong tu che ra bat ky luat nao khac.\n"
            "6) Bat buoc phai giai thich dua tren Nguyen tac Thu bac hoac Thoi gian de tang tinh thuyet phuc neu ket luan la co xung dot.\n\n"
            f"KET QUA KHUYEN NGHI THEO CHI BAO HE THONG: {'CO XUNG DOT' if decision == 'CO' else 'KHONG XUNG DOT'}.\n"
            "Dong dau tien bao cao phai bat dau bang: 'Ket luan: ...'.\n\n"
            "GOI Y KHOAN CACH XUNG DOT (Giup LLM tham khao): \n"
            f"{difference_hints}\n\n"
            "CAP DOI CHIEU DE XUAT THEO DO CHINH XAC (hybrid context):\n"
            f"{candidate_block}\n\n"
            f"CHU DE CAN XEM XET: {topic_query}\n\n"
            "DINH DANG TRA LOI CUOI CUNG:\n"
            "- Ket luan: CO XUNG DOT / KHONG XUNG DOT (1 dong)\n"
            "- Ly do chinh (2-3 cau tu nhien, ep LLM phan tich doc vi theo nguyen tac Thu bac / Thoi gian o tren neu co mau thuan [E?] vs [E?])\n"
            "- Ngu canh dan chung (Liet ke ngan gon cac [E])\n"
            "- Khuyen nghi ap dung dieu luat nao (1-2 cau)."
        )

        report = self.generator.answer(question=question, context_blocks=context_blocks, max_new_tokens=380, temperature=0.15)
        if self._looks_like_template_output(report):
            report = self._build_fallback_report(topic_query, docs, candidates, decision)
            
        for i, row in docs.iterrows():
            report = report.replace(f"[E{i + 1}]", f"{row['article']}")
            report = report.replace(f"E{i + 1}", f"{row['article']}")
        report = report.replace("[A1]", "khoản tham chiếu")

        context_summary = self._build_conflict_context_summary(docs)
        return report, docs, context_summary
