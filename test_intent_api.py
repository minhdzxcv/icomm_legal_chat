#!/usr/bin/env python3
"""Test intent classification via API."""

import requests
import json

base_url = "http://localhost:8000"

test_queries = [
    "chào fen",
    "chào bạn",
    "hôm nay thế nào",
    "quy định bầu cử là gì",
    "so sánh luật lao động",
    "phân tích xung đột quy định"
]

print("=" * 70)
print("TESTING INTENT CLASSIFICATION VIA API")
print("=" * 70)

for query in test_queries:
    try:
        response = requests.get(f"{base_url}/debug/intent", params={"question": query}, timeout=10)
        result = response.json()
        intent = result.get("intent", "ERROR")
        print(f"'{query}' → {intent}")
    except Exception as e:
        print(f"'{query}' → ERROR: {e}")

print("=" * 70)
