from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class LegalGenerator:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map="auto" if device == "cuda" else None,
        )

        if device != "cuda":
            self.model.to(device)

    def answer(self, question: str, context_blocks: list[str], max_new_tokens: int = 320, temperature: float = 0.1) -> str:
        import time
        t0 = time.time()
        
        context = "\n\n".join(context_blocks)
        prompt = (
            "<|im_start|>system\n"
            "Bạn là trợ lý pháp lý chuyên nghiệp. Bạn PHẢI trả lời CHÍNH XÁC dựa HOÀN TOÀN trên Nội dung pháp luật được cung cấp dưới đây.\n"
            "LUẬT LỆ:\n"
            "- Chỉ sử dụng thông tin từ Nội dung pháp luật, KHÔNG tự sáng tạo.\n"
            "- PHẢI nêu cụ thể Điều khoản, Khoản liên quan.\n"
            "- Nếu không tìm thấy thông tin, nói rõ 'Thông tin không có trong dữ liệu'.\n"
            "- KHÔNG ĐƯỢC nói 'Tôi không thể', 'Không có khả năng truy cập', hoặc từ chối.\n"
            "- TRẢ LỜI TRỰC TIẾP VÀ CHI TIẾT từ các Điều khoản được cung cấp.\n"
            f"NỘI DUNG PHÁP LUẬT:\n{context}<|im_end|>\n"
            "<|im_start|>user\n"
            f"{question}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                repetition_penalty=1.1,
                temperature=temperature,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        t_gen = time.time() - t0
        input_len = inputs.input_ids.shape[1]
        output_len = out[0].shape[0] - input_len
        speed = output_len / t_gen if t_gen > 0 else 0
        print(f"[PERF] LLM Generation completed in {t_gen:.3f}s (Speed: {speed:.1f} tokens/sec, Output: {output_len} tokens)")

        decoded = self.tokenizer.decode(out[0], skip_special_tokens=True)
        if "assistant\n" in decoded:
            return decoded.split("assistant\n")[-1].strip()
        return decoded.strip()
