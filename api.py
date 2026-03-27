from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.legal_chatbot.chatbot import LegalRAGChatbot
from src.legal_chatbot.config import AppConfig


class AskRequest(BaseModel):
    question: str
    top_k: int = 3


class ConflictRequest(BaseModel):
    topic: str
    top_k: int = 5


app = FastAPI(title="Legal Chatbot API", version="1.0.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cfg = AppConfig(num_docs=100)
bot = LegalRAGChatbot(cfg)
_initialized = False


@app.on_event("startup")
def startup_event() -> None:
    global _initialized
    if not _initialized:
        bot.build_or_load(force_rebuild=False)
        _initialized = True


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask")
def ask_legal(req: AskRequest) -> dict:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    try:
        return bot.ask(req.question, k=max(1, req.top_k))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/conflict")
def analyze_conflict(req: ConflictRequest) -> dict:
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")

    try:
        return bot.analyze_conflict(req.topic, k=max(2, req.top_k))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/debug/intent")
def debug_intent(question: str) -> dict:
    """Debug endpoint to test intent classification."""
    from src.legal_chatbot.intent_classifier import intent_classifier
    
    intent = intent_classifier.classify(question)
    return {
        "question": question,
        "intent": intent
    }


@app.post("/upload")
async def upload_legal_file(file: UploadFile = File(...), title: str | None = Form(default=None)) -> dict:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        temp_path = tmp.name

    try:
        return bot.ingest_file(temp_path, title=title or file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        Path(temp_path).unlink(missing_ok=True)
