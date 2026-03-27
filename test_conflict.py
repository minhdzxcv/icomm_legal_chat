#!/usr/bin/env python3
import requests

payload = {
    "topic": "Xung đột quy định về mức phạt hành vi trốn thuế",
    "top_k": 5,
}

resp = requests.post("http://127.0.0.1:8000/conflict", json=payload, timeout=600)
resp.raise_for_status()
result = resp.json()

print("=== CONFLICT RESULT ===")
print(f"Intent: {result.get('intent')}")
print(f"Sources found: {len(result.get('sources', []))}")
print(f"\nAnswer (first 500 chars):\n{result.get('answer', '')[:500]}...")

if result.get("sources"):
    print("\n=== SOURCES ===")
    for i, src in enumerate(result["sources"], 1):
        print(f"{i}. {src.get('evidence_id')} | {src.get('title')} | {src.get('article')} | rerank={src.get('rerank_score')}")
