#!/usr/bin/env python3
import requests
import json

query = "tôi muốn tìm hiểu về quy định xử phạt vi phạm về hành chính về thuế, hóa đơn"
resp = requests.post("http://127.0.0.1:8000/ask", json={"question": query, "top_k": 3})
result = resp.json()

print("=== ASK RESULT ===")
print(f"Intent: {result.get('intent')}")
print(f"\nAnswer (first 300 chars):\n{result.get('answer')[:300]}...")
print(f"\n\nSources found: {len(result.get('sources', []))}")
if result.get("sources"):
    print("\n=== SOURCE DETAILS ===")
    for i, src in enumerate(result["sources"], 1):
        print(f"\nSource {i}:")
        print(f"  Title: {src.get('title')}")
        print(f"  Article: {src.get('article')}")
        print(f"  Text: {src.get('text')[:150]}...")
else:
    print("\n⚠️  NO SOURCES RETURNED BY API!")
