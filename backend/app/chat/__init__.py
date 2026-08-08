"""
AI Chat Security Assistant
===========================
Enterprise RAG-based chat assistant enabling natural-language queries
against the scam detection platform.

Users can ask questions such as:
  - "Why is this scam?"
  - "Explain this URL"
  - "Generate investigation report"
  - "Show today's attacks"
  - "Compare two predictions"

The assistant uses Retrieval-Augmented Generation (RAG) over past
predictions, analyses, reports, and threat intelligence records.

Feature Flag: ENABLE_CHAT (default: true)
"""

from .config import ChatConfig
from .models import (
    ChatMessage,
    ChatSession,
    ChatDocumentChunk,
    ChatRole,
    ChatIntent,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessageOut,
    ChatSessionOut,
    ChatIntentResponse,
)
from .service import ChatAssistantService
from .router import router

__all__ = [
    "ChatConfig",
    "ChatMessage",
    "ChatSession",
    "ChatDocumentChunk",
    "ChatRole",
    "ChatIntent",
    "ChatRequest",
    "ChatResponse",
    "ChatMessageOut",
    "ChatSessionOut",
    "ChatIntentResponse",
    "ChatAssistantService",
    "router",
]
