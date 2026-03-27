from __future__ import annotations

import argparse

from src.legal_chatbot.chatbot import LegalRAGChatbot
from src.legal_chatbot.config import AppConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Legal chatbot with RAG + conflict analysis")
    parser.add_argument("--num-docs", type=int, default=100, help="Number of source docs from dataset")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild parquet/index artifacts")
    parser.add_argument("--question", type=str, default="", help="Question for RAG QA")
    parser.add_argument("--conflict-topic", type=str, default="", help="Topic for conflict/chong cheo analysis")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cfg = AppConfig(num_docs=args.num_docs)
    bot = LegalRAGChatbot(cfg)
    bot.build_or_load(force_rebuild=args.rebuild)

    if args.question:
        result = bot.ask(args.question, k=3)
        print("\n=== ANSWER ===")
        print(result["answer"])
        print("\n=== SOURCES ===")
        for i, src in enumerate(result["sources"], start=1):
            print(f"{i}. {src['title']} ({src['article']})")
            print(f"   {src['url']}")

    if args.conflict_topic:
        result = bot.analyze_conflict(args.conflict_topic, k=5)
        print("\n=== CONFLICT REPORT ===")
        print(result["report"])
        print("\n=== SOURCES ===")
        for i, src in enumerate(result["sources"], start=1):
            print(f"{i}. {src['title']} ({src['article']})")
            print(f"   {src['url']}")

    if not args.question and not args.conflict_topic:
        print("No action requested. Use --question or --conflict-topic.")


if __name__ == "__main__":
    main()
