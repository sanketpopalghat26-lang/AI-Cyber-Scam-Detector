"""
AI Chat Security Assistant Service
====================================
RAG-based chat assistant implementation.

The service:
  1. Detects the user's intent from the natural-language query.
  2. Retrieves relevant context from the RAG document store (scans,
     reports, threat intelligence records, investigations).
  3. Generates a grounded response using the retrieved context.
  4. Persists the conversation history.

External LLM providers (OpenAI, Anthropic, Azure) are supported behind a
provider interface. When no provider API key is configured, an internal
template-based generator is used, keeping the module fully functional
out-of-the-box.
"""

import re
import time
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlmodel import Session, select

from ..core.audit import get_audit_logger
from ..core.guardrails import get_guardrails
from .config import ChatConfig
from .models import (
    ChatDocumentChunk,
    ChatIntent,
    ChatMessage,
    ChatRole,
    ChatSession,
)

# =============================================================================
# Internal RAG / Generation
# =============================================================================


class _InternalGenerator:
    """
    Internal template-based generator used when no external LLM is configured.

    Produces grounded answers from retrieved context without any external
    API dependency. Keeps the module functional in offline / dev environments.
    """

    INTENT_OPENINGS = {
        ChatIntent.EXPLAIN_PREDICTION: (
            "Here's why the content was classified the way it was"
        ),
        ChatIntent.EXPLAIN_URL: "Here is the reputation analysis for that URL/domain",
        ChatIntent.GENERATE_REPORT: "Here is a summary report from the available records",
        ChatIntent.TODAY_ATTACKS: "Here is an overview of recent activity",
        ChatIntent.COMPARE_PREDICTIONS: "Here is a comparison of the matched records",
        ChatIntent.THREAT_LOOKUP: "Here is the threat intelligence result",
        ChatIntent.HELP: (
            "I can help you understand scam detections, explain URLs, "
            "generate reports, review recent attacks, and compare predictions. "
            "Try asking: 'Why is this scam?', 'Explain this URL', "
            "'Show today's attacks', or 'Compare two predictions'."
        ),
        ChatIntent.GENERAL: "Here is what I found",
    }

    def generate(
        self,
        query: str,
        intent: ChatIntent,
        context: list[dict[str, Any]],
        config: ChatConfig,
    ) -> str:
        """Generate a grounded response from retrieved context."""
        opening = self.INTENT_OPENINGS.get(intent, "Here is what I found")

        if not context:
            if intent == ChatIntent.HELP:
                return opening
            return (
                f"{opening}, but I could not find specific records matching your "
                f"query: '{query[:120]}'. Try providing more detail, or ask about "
                f"a recent prediction, URL, threat, or investigation."
            )

        lines = [f"{opening}:", ""]
        for i, doc in enumerate(context[: config.k], start=1):
            label = doc.get("label") or doc.get("source_type", "record")
            content = doc.get("content", "")
            score = doc.get("score", 0.0)
            lines.append(f"{i}. [{label} - relevance {score:.0%}]")
            if content:
                lines.append(f"   {content[:300]}")
            lines.append("")

        lines.append(
            "Note: This response is grounded in the retrieved platform records. "
            "Always verify critical findings before acting."
        )
        text = "\n".join(lines)
        return text[: config.max_response_chars]


class _ExternalLLMProvider:
    """
    Adapter for external LLM providers (OpenAI, Anthropic, Azure, generic).

    Implements a minimal chat-completions call. This is intentionally kept
    modular so any provider can be wired in without changing the service.
    """

    def __init__(self, config: ChatConfig):
        self.config = config

    async def generate(
        self, query: str, intent: ChatIntent, context: list[dict[str, Any]]
    ) -> str | None:
        """Call the configured external LLM (best-effort)."""
        try:
            import httpx

            # Build context block
            context_block = "\n".join(
                f"- {d.get('content', '')[:500]}" for d in context[: self.config.k]
            )
            system = (
                "You are the AI Cyber Security Assistant for an enterprise "
                "scam detection platform. Answer using only the provided "
                "retrieved context. Be concise, accurate, and security-focused."
            )
            user = f"Context:\n{context_block}\n\nQuestion: {query}"

            # Generic OpenAI-compatible endpoint
            payload = {
                "model": self.config.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 500,
            }
            headers = {"Authorization": f"Bearer {self.config.llm_api_key}"}
            endpoint = self.config.llm_endpoint or "https://api.openai.com/v1/chat/completions"

            async with httpx.AsyncClient(timeout=self.config.llm_timeout) as client:
                resp = await client.post(
                    endpoint, json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:  # pragma: no cover - best-effort external call
            logger.warning(f"External LLM call failed, falling back to internal: {e}")
            return None


# =============================================================================
# Retrieval (RAG)
# =============================================================================


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase alpha-numeric tokens."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class ChatAssistantService:
    """RAG-based chat assistant service."""

    def __init__(self, config: ChatConfig | None = None):
        self.config = config or ChatConfig.from_env()
        self.internal_generator = _InternalGenerator()
        self.external_llm = _ExternalLLMProvider(self.config)

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------
    def detect_intent(self, message: str) -> tuple[ChatIntent, float, list[str]]:
        """Detect the intent of a user query based on keyword matching."""
        lowered = message.lower()
        best_intent = ChatIntent.GENERAL
        best_score = 0.0
        best_keywords: list[str] = []

        for intent_name, keywords in self.config.intent_keywords.items():
            matched = [kw for kw in keywords if kw in lowered]
            if matched:
                score = min(1.0, len(matched) / 2.0)
                if score > best_score:
                    best_intent = ChatIntent(intent_name)
                    best_score = score
                    best_keywords = matched

        return best_intent, best_score, best_keywords

    # ------------------------------------------------------------------
    # Document ingestion
    # ------------------------------------------------------------------
    def index_document(
        self,
        session: Session,
        source_type: str,
        source_id: int | None,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatDocumentChunk | None:
        """Index a document chunk for RAG retrieval."""
        if not content.strip():
            return None
        chunk = ChatDocumentChunk(
            source_type=source_type,
            source_id=source_id,
            content=content,
            tokens_count=len(_tokenize(content)),
            metadata_json=metadata or {},
        )
        session.add(chunk)
        return chunk

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def retrieve(
        self,
        session: Session,
        query: str,
        k: int | None = None,
        source_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve the most relevant documents for a query."""
        k = k or self.config.k
        query_tokens = _tokenize(query)

        stmt = select(ChatDocumentChunk)
        if source_types:
            stmt = stmt.where(ChatDocumentChunk.source_type.in_(source_types))
        chunks = session.exec(stmt).all()

        scored: list[dict[str, Any]] = []
        for chunk in chunks:
            # Lexical overlap score
            chunk_tokens = _tokenize(chunk.content)
            overlap = len(query_tokens & chunk_tokens)
            lexical_score = overlap / max(len(query_tokens), 1)

            # Semantic score if embeddings are available
            semantic_score = 0.0
            if chunk.embedding and query_tokens:
                # Simple hash-based pseudo-embedding for the query
                query_emb = [
                    float(hash(w) % 1000) / 1000.0 for w in query_tokens
                ]
                semantic_score = _cosine_similarity(query_emb, chunk.embedding) * 0.5

            score = min(1.0, lexical_score + semantic_score)
            if score < self.config.similarity_threshold:
                continue

            scored.append(
                {
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                    "content": chunk.content,
                    "score": round(score, 4),
                    "metadata": chunk.metadata_json or {},
                    "label": (chunk.metadata_json or {}).get("label", chunk.source_type),
                    "created_at": chunk.created_at,
                }
            )

        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:k]

    # ------------------------------------------------------------------
    # Response generation
    # ------------------------------------------------------------------
    async def _generate_response(
        self, query: str, intent: ChatIntent, context: list[dict[str, Any]]
    ) -> tuple[str, str]:
        """Generate a response using external LLM if configured, else internal."""
        if self.config.is_llm_configured():
            external = await self.external_llm.generate(query, intent, context)
            if external:
                return external, self.config.llm_model
        return (
            self.internal_generator.generate(query, intent, context, self.config),
            self.config.default_model,
        )

    # ------------------------------------------------------------------
    # Main chat flow
    # ------------------------------------------------------------------
    async def chat(
        self,
        session: Session,
        user_id: int | None,
        message: str,
        session_id: int | None = None,
        source: str = "chat",
    ) -> dict[str, Any]:
        """Process a chat message and return the assistant's response."""
        start = time.time()

        # AI guardrails: screen the input for prompt injection / jailbreak
        guardrails = get_guardrails()
        input_check = guardrails.evaluate_input(message)
        guardrails.audit(
            input_check,
            context={"actor": str(user_id) if user_id else "anonymous", "resource": "chat"},
        )
        if not input_check.allowed:
            # Reject hostile input with a defensive, non-revealing response.
            refusal = (
                "I can't process that request because it appears to attempt an "
                "unsafe prompt manipulation. Please rephrase your question about "
                "scam detection, URLs, reports, or threats."
            )
            return {
                "message": None,
                "session_id": session_id,
                "intent": ChatIntent.GENERAL,
                "response": refusal,
                "sources": [],
                "confidence": 0.0,
                "model": self.config.default_model,
                "processing_time_ms": round((time.time() - start) * 1000, 2),
                "matched_keywords": [],
                "guardrail": input_check.to_dict(),
            }

        intent, intent_score, matched_keywords = self.detect_intent(message)

        # Resolve or create chat session
        if session_id:
            chat_session = session.get(ChatSession, session_id)
            if chat_session is None:
                raise ValueError(f"Chat session {session_id} not found")
        else:
            # Derive a short title from the first message
            title = message[:60] + ("..." if len(message) > 60 else "")
            chat_session = ChatSession(user_id=user_id, title=title)
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

        # Save user message
        user_msg = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.USER,
            content=message,
            intent=intent,
        )
        session.add(user_msg)

        # Retrieve context
        context = self.retrieve(session, message)

        # Index the user message as a retrievable document (enables follow-ups)
        self.index_document(
            session,
            source_type="user_message",
            source_id=user_msg.id,
            content=message,
            metadata={"intent": intent.value, "user_id": user_id},
        )

        # Generate response
        response_text, model = await self._generate_response(message, intent, context)

        # Save assistant message
        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role=ChatRole.ASSISTANT,
            content=response_text,
            intent=intent,
            retrieved_context=[{k: v for k, v in d.items()} for d in context],
            confidence=round(intent_score, 3) if intent_score > 0 else 0.5,
            model=model,
        )
        session.add(assistant_msg)
        session.commit()
        session.refresh(user_msg)
        session.refresh(assistant_msg)

        processing_time_ms = (time.time() - start) * 1000

        # Build message DTO
        message_dto = {
            "id": assistant_msg.id,
            "session_id": assistant_msg.session_id,
            "role": assistant_msg.role,
            "content": assistant_msg.content,
            "intent": assistant_msg.intent,
            "retrieved_context": context,
            "confidence": assistant_msg.confidence,
            "model": assistant_msg.model,
            "created_at": assistant_msg.created_at.isoformat(),
        }

        # Audit log
        get_audit_logger().log(
            action="chat.message",
            actor=str(user_id) if user_id else "anonymous",
            resource="chat_session",
            resource_id=str(chat_session.id),
            result="success",
            details={
                "intent": intent.value,
                "context_docs": len(context),
                "processing_time_ms": round(processing_time_ms, 2),
            },
        )

        return {
            "message": message_dto,
            "session_id": chat_session.id,
            "intent": intent,
            "response": response_text,
            "sources": context,
            "confidence": message_dto["confidence"],
            "model": model,
            "processing_time_ms": round(processing_time_ms, 2),
            "matched_keywords": matched_keywords,
        }

    # ------------------------------------------------------------------
    # Session retrieval helpers
    # ------------------------------------------------------------------
    def get_session_messages(
        self, session: Session, session_id: int, limit: int = 50
    ) -> list[ChatMessage]:
        """Get recent messages for a chat session in chronological order."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        msgs = session.exec(stmt).all()
        return list(reversed(msgs))

    def list_sessions(
        self, session: Session, user_id: int | None, limit: int = 20
    ) -> list[ChatSession]:
        """List chat sessions for a user."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.is_active == True)  # noqa: E712
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        if user_id:
            stmt = stmt.where(ChatSession.user_id == user_id)
        return list(session.exec(stmt).all())

    def health_check(self) -> dict[str, Any]:
        """Return module health status."""
        return {
            "status": "healthy",
            "module": "chat",
            "enabled": self.config.enabled,
            "llm_provider": self.config.llm_provider,
            "llm_configured": self.config.is_llm_configured(),
            "rag_top_k": self.config.k,
            "timestamp": datetime.now(UTC).isoformat(),
        }
