"""
AI Chat Security Assistant Configuration
==========================================
Centralized configuration for the RAG-based chat assistant.
All secrets and settings are loaded from environment variables.
"""

import os
from dataclasses import dataclass, field


@dataclass
class ChatConfig:
    """Configuration for the AI Chat Security Assistant."""

    enabled: bool = os.getenv("ENABLE_CHAT", "true").lower() == "true"

    # RAG / retrieval settings
    k: int = int(os.getenv("CHAT_RAG_TOP_K", "5"))  # Number of retrieved docs
    similarity_threshold: float = float(
        os.getenv("CHAT_RAG_SIMILARITY_THRESHOLD", "0.15")
    )
    max_context_tokens: int = int(os.getenv("CHAT_MAX_CONTEXT_TOKENS", "2000"))

    # Generation
    max_response_chars: int = int(os.getenv("CHAT_MAX_RESPONSE_CHARS", "4000"))
    default_model: str = os.getenv("CHAT_MODEL", "internal-rag")

    # Session management
    session_idle_ttl_seconds: int = int(
        os.getenv("CHAT_SESSION_IDLE_TTL_SECONDS", "1800")
    )  # 30 minutes
    max_history_messages: int = int(
        os.getenv("CHAT_MAX_HISTORY_MESSAGES", "20")
    )

    # External LLM provider (optional, keep modular)
    llm_provider: str = os.getenv("CHAT_LLM_PROVIDER", "internal")
    # e.g. "openai", "anthropic", "azure_openai", "internal"
    llm_api_key: str | None = os.getenv("CHAT_LLM_API_KEY")
    llm_model: str = os.getenv("CHAT_LLM_MODEL", "gpt-4o-mini")
    llm_endpoint: str | None = os.getenv("CHAT_LLM_ENDPOINT")
    llm_timeout: int = int(os.getenv("CHAT_LLM_TIMEOUT", "30"))

    # Rate limiting
    chat_rate_limit: int = int(os.getenv("CHAT_RATE_LIMIT", "60"))
    chat_rate_window: int = int(os.getenv("CHAT_RATE_WINDOW", "60"))

    # Intent detection keywords
    intent_keywords: dict[str, list[str]] = field(
        default_factory=lambda: {
            "explain_prediction": ["why is", "explain", "why was", "why this", "reason"],
            "explain_url": ["url", "link", "domain", "website", "site"],
            "generate_report": ["report", "generate report", "investigation report", "summary"],
            "today_attacks": ["today", "attacks", "recent", "latest", "trend"],
            "compare_predictions": ["compare", "versus", "vs", "difference between"],
            "threat_lookup": ["threat", "ioc", "ip", "reputation", "malicious"],
            "help": ["help", "what can you", "how do i", "capabilities"],
        }
    )

    @classmethod
    def from_env(cls) -> "ChatConfig":
        """Create configuration from environment variables."""
        return cls()

    def is_llm_configured(self) -> bool:
        """Check if an external LLM provider is configured."""
        return bool(self.llm_api_key) and self.llm_provider != "internal"
