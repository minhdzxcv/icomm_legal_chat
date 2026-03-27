#!/usr/bin/env python3
"""Debug script để kiểm tra intent classification."""

from src.legal_chatbot.intent_classifier import intent_classifier

# Test cases
test_queries = [
    "chào fen",
    "chào bạn",
    "quy định bầu cử là gì?",
    "hôm nay thế nào?",
    "so sánh luật lao động vs bảo hiểm",
    "chào, tôi muốn biết về quy định bầu cử",
    "Phân tích xung đột giữa quy định mới và quy định cũ",
]

print("=" * 60)
print("TESTING INTENT CLASSIFIER")
print("=" * 60)

for query in test_queries:
    print(f"\n❓ Query: '{query}'")
    intent = intent_classifier.classify(query)
    print(f"➜ Intent: {intent}")

print("\n" + "=" * 60)
