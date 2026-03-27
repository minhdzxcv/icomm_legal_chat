#!/usr/bin/env python3
from src.legal_chatbot.config import AppConfig
from src.legal_chatbot.chatbot import LegalRAGChatbot

q = "xung đột quy định về mức phạt hành vi trốn thuế"

bot = LegalRAGChatbot(AppConfig(num_docs=100))
bot.build_or_load(False)
r = bot.analyze_conflict(q, k=5)

print("=== QUERY ===")
print(q)
print("\n=== INTENT ===")
print(r.get("intent"))
print("\n=== ANSWER ===")
print(r.get("answer"))
print("\n=== CONFLICT CONTEXT (SHORT) ===")
print(r.get("conflict_context", ""))
print("\n=== SOURCES (TOP 5) ===")
for i, s in enumerate(r.get("sources", []), 1):
    print(f"{i}. [{s.get('evidence_id')}] {s.get('title')} - {s.get('article')}")
    print(f"   conflict_text: {str(s.get('conflict_text', ''))[:220]}")
    print(f"   url: {s.get('url')}")
