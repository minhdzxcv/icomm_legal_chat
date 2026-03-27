from __future__ import annotations

from typing import Literal
import re

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    HAS_LLM = True
except Exception:
    HAS_LLM = False


class IntentClassifier:
    """Hybrid intent classifier: keyword scoring (primary) + LLM fallback for edge cases."""
    
    # Conflict analysis keywords (highest priority)
    CONFLICT_KEYWORDS = {
        # Comparison/Analysis
        "so sánh", "xung đột", "tranh chấp", "mâu thuẫn", "phân tích",
        "đối chiếu", "tương tự", "giống nhau", "khác nhau", "khác biệt",
        
        # Legal conflicts
        "quy định mâu thuẫn", "mâu thuẫn pháp lệnh", "quy định khác nhau",
        "xung đột pháp lệnh", "điểm khác", "điểm giống",
        
        # Analysis verbs
        "phân tích", "tổng hợp", "đánh giá", "cân nhắc"
    }
    
    # Legal Q&A keywords
    LEGAL_KEYWORDS = {
        # Regulations/Laws
        "quy định", "luật", "pháp lệnh", "quy chế", "thông tư", "nghị định",
        "nghị quyết", "quyết định", "công văn", "chỉ thị", "hướng dẫn",
        
        # Legal concepts
        "hành chính", "pháp luật", "pháp lý", "trách nhiệm pháp lý",
        "vi phạm", "xử phạt", "tiền phạt", "hình phạt",
        
        # Legal domains
        "lao động", "bảo hiểm", "thuế", "giao dịch", "hợp đồng", "bất động sản",
        "doanh nghiệp", "công ty", "kinh doanh", "giấy phép", "đăng ký",
        "xã hội", "y tế", "giáo dục", "xây dựng", "giao thông",
        
        # Question intent
        "hỏi về", "biết về", "là gì", "như thế nào", "thế nào"
    }
    
    # General conversation keywords
    GENERAL_KEYWORDS = {
        # Greetings
        "chào", "xin chào", "hi", "hello", "hey",
        
        # Personal
        "tôi", "bạn", "bạn là", "tôi là", "ai là",
        
        # Pleasantries
        "cảm ơn", "thanks", "cơm chưa", "mọi người", "bạn khỏe không",
        
        # Time/Weather
        "hôm nay", "hôm qua", "hôm sau", "thế nào", "tó te", "alo", "ơi",
        
        # Filler
        "ơ kìa", "làm gì", "sao", "gì", "à", "ơi"
    }
    
    def __init__(self):
        """Initialize hybrid classifier (keyword primary + LLM fallback)."""
        self.use_llm = False
        self.model = None
        self.tokenizer = None
        self.confidence_threshold = 0.5  # Lower threshold: trust keyword scoring more
        
        # Try to load LLM for fallback
        if HAS_LLM:
            try:
                self.model_name = "Qwen/Qwen2.5-0.5B-Instruct"
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype="auto",
                    device_map="auto"
                )
                self.use_llm = True
                print("✓ Hybrid: Keyword primary (fast) + LLM fallback (edge cases)")
            except Exception as e:
                print(f"✓ Hybrid: Keyword-only (LLM not available)")
        else:
            print("✓ Hybrid: Keyword-only (transformers not installed)")
    
    def _chunk_query(self, query: str) -> list[str]:
        """
        Split query into logical chunks (sentences/questions).
        
        Returns:
            List of chunks/sentences
        """
        # Split by Vietnamese sentence endings and punctuation
        chunks = re.split(r'[。\.？!？！\n,;]+', query)
        
        # Clean and filter chunks
        cleaned = []
        for chunk in chunks:
            chunk = chunk.strip()
            if len(chunk) > 2:  # Ignore very short fragments
                cleaned.append(chunk)
        
        return cleaned if cleaned else [query]
    
    def _score_keywords(self, text: str, keywords: set[str]) -> int:
        """
        Count keyword matches with weighting.
        
        Args:
            text: Query text to search
            keywords: Set of keywords to match
            
        Returns:
            Score (count of matched keywords)
        """
        text_lower = text.lower()
        score = 0
        matched_keywords = []
        
        for keyword in keywords:
            # Count occurrences of this keyword
            count = text_lower.count(keyword)
            if count > 0:
                score += count
                matched_keywords.append((keyword, count))
        
        return score
    
    def _classify_chunk(self, chunk: str) -> tuple[Literal["general", "legal_qa", "conflict_analysis"], int]:
        """
        Classify a chunk using keyword scoring.
        
        Returns:
            (intent, max_score) - score indicates confidence
        """
        chunk_lower = chunk.lower().strip()
        
        # Calculate scores for each category
        conflict_score = self._score_keywords(chunk_lower, self.CONFLICT_KEYWORDS)
        legal_score = self._score_keywords(chunk_lower, self.LEGAL_KEYWORDS)
        general_score = self._score_keywords(chunk_lower, self.GENERAL_KEYWORDS)
        
        # CRITICAL DEBUG
        if len(chunk_lower) > 5:
            print(f"  🔍 chunk='{chunk_lower[:40]}...' C:{conflict_score} L:{legal_score} G:{general_score}")
        
        # Priority: conflict > legal > general
        max_score = max(conflict_score, legal_score, general_score)
        
        if conflict_score > 0 and conflict_score >= legal_score and conflict_score >= general_score:
            return "conflict_analysis", max_score
        elif legal_score > 0 and legal_score > general_score:
            return "legal_qa", max_score
        elif general_score > 0:
            return "general", max_score
        
        # No keywords matched
        if "?" in chunk or "là gì" in chunk_lower:
            return "legal_qa", 0.5  # Low confidence: assume legal question
        
        return "general", 0
    
    def _classify_chunk_llm(self, chunk: str) -> Literal["general", "legal_qa", "conflict_analysis"]:
        """Classify chunk using LLM (fallback for low-confidence keyword cases)."""
        if not self.use_llm or not self.model:
            return "general"
        
        try:
            prompt = f"""Phân loại câu này: "{chunk}"

Đáp án: general, legal_qa, hoặc conflict_analysis
- general: Chào hỏi, hỏi thường
- legal_qa: Hỏi về pháp luật, quy định
- conflict_analysis: Phân tích xung đột, so sánh quy định

Chỉ trả 1 từ."""
            
            inputs = self.tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=5,
                    temperature=0.1,
                    top_p=0.9
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True).lower().strip()
            
            if "conflict" in response:
                return "conflict_analysis"
            elif "legal" in response:
                return "legal_qa"
            else:
                return "general"
        except Exception:
            return "general"
    
    def classify(self, query: str) -> Literal["general", "legal_qa", "conflict_analysis"]:
        """
        Hybrid intent classification: keyword scoring (primary) + LLM fallback.
        
        Process:
        1. Use keyword scoring (fast, <5ms)
        2. If confidence < threshold, use LLM (slow but accurate)
        3. Return result
        
        Returns:
            "conflict_analysis": Analyzing conflicts/comparing regulations
            "legal_qa": Asking about laws/regulations
            "general": General conversation
        """
        # Edge case
        if len(query.strip()) < 3:
            return "general"
        
        # Step 1: Chunk the query
        chunks = self._chunk_query(query)
        
        # Step 2: Classify each chunk with keywords
        chunk_results = []
        max_keyword_score = 0
        
        for chunk in chunks:
            intent, score = self._classify_chunk(chunk)
            chunk_results.append((intent, score))
            max_keyword_score = max(max_keyword_score, score)
        
        # Step 3: Aggregate keyword results
        conflict_count = sum(1 for intent, _ in chunk_results if intent == "conflict_analysis")
        legal_count = sum(1 for intent, _ in chunk_results if intent == "legal_qa")
        general_count = len(chunk_results) - conflict_count - legal_count
        
        # Determine primary intent from keywords
        if conflict_count > 0:
            primary_intent = "conflict_analysis"
        elif legal_count > 0:
            primary_intent = "legal_qa"
        else:
            primary_intent = "general"
        
        print(f"  📊 Final: conflict={conflict_count} legal={legal_count} general={general_count}, max_score={max_keyword_score}")
        
        # Step 4: Check confidence level
        # If high confidence in keywords, use it directly
        if max_keyword_score >= self.confidence_threshold:
            print(f"  ✅ Using keyword result: {primary_intent} (score={max_keyword_score})")
            return primary_intent
        
        # Low confidence: use LLM fallback for better accuracy
        if self.use_llm and len(query) > 5:
            print(f"  ⚠️  Low confidence ({max_keyword_score}), invoking LLM...")
            llm_result = self._classify_chunk_llm(query)
            print(f"  🤖 LLM result: {llm_result}")
            return llm_result
        
        # No LLM or too short: use keyword result (even if low confidence)
        print(f"  ✅ Using fallback (no LLM): {primary_intent}")
        return primary_intent


# Singleton instance
intent_classifier = IntentClassifier()
