"""Validate Phase 5 chat module compiles and imports correctly."""
import os
import sys

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./dev.db")
os.environ.setdefault("ENABLE_CACHE", "false")
os.environ.setdefault("ENABLE_METRICS", "false")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

errors = []


def check(name, fn):
    try:
        fn()
        print(f"[OK] {name}")
    except Exception as e:  # noqa: BLE001
        errors.append((name, e))
        print(f"[FAIL] {name}: {e}")


# 1. Compile all chat module files
def check_compile():
    import py_compile

    base = os.path.join("backend", "app", "chat")
    for f in os.listdir(base):
        if f.endswith(".py"):
            py_compile.compile(os.path.join(base, f), doraise=True)


check("chat module compile", check_compile)


# 2. Import chat models
def check_models():
    from app.chat.models import (
        ChatDocumentChunk,
        ChatIntent,
        ChatMessage,
        ChatRole,
        ChatSession,
    )

    assert ChatMessage.__tablename__ == "chat_messages"
    assert ChatSession.__tablename__ == "chat_sessions"
    assert ChatDocumentChunk.__tablename__ == "chat_document_chunks"
    assert ChatRole.USER.value == "user"
    assert ChatIntent.EXPLAIN_PREDICTION.value == "explain_prediction"


check("chat models import", check_models)


# 3. Import chat schemas
def check_schemas():
    from app.chat.schemas import ChatRequest, ChatResponse, ChatIntentResponse

    req = ChatRequest(message="Why is this scam?", source="test")
    assert req.message == "Why is this scam?"
    assert req.source == "test"
    assert req.session_id is None


check("chat schemas import/validate", check_schemas)


# 4. Import chat config
def check_config():
    from app.chat.config import ChatConfig

    cfg = ChatConfig.from_env()
    assert cfg.enabled is True
    assert cfg.k > 0
    assert cfg.max_response_chars > 0
    assert cfg.is_llm_configured() is False  # no API key in test env


check("chat config import", check_config)


# 5. Import chat service
def check_service():
    from app.chat.service import ChatAssistantService

    svc = ChatAssistantService()
    intent, score, keywords = svc.detect_intent("Why is this scam?")
    assert intent.value == "explain_prediction"
    assert score > 0
    assert keywords


check("chat service import + intent detection", check_service)


# 6. Import chat router
def check_router():
    from app.chat.router import router

    routes = [r.path for r in router.routes]
    assert "/api/chat" in routes
    assert "/api/chat/sessions" in routes
    assert "/api/chat/sessions/{session_id}/messages" in routes
    assert "/api/chat/detect-intent" in routes
    assert "/api/chat/health" in routes


check("chat router import + routes", check_router)


# 7. Import main app (registers chat router)
def check_main():
    from app.main import app

    # Verify chat router is registered.
    # app.routes may contain _IncludedRouter wrappers alongside APIRoute
    # objects depending on the Starlette version. Extract paths defensively.
    def _collect(route, out):
        p = getattr(route, "path", None)
        if p:
            out.append(p)
        # _IncludedRouter exposes the original APIRouter whose .routes hold
        # the concrete APIRoute paths.
        original = getattr(route, "original_router", None)
        if original is not None:
            for r in getattr(original, "routes", []):
                p2 = getattr(r, "path", None)
                if p2:
                    out.append(p2)
        sub = getattr(route, "routes", None)
        if sub:
            for r in sub:
                _collect(r, out)

    paths: list[str] = []
    for r in app.routes:
        _collect(r, paths)
    assert "/api/chat" in paths
    assert "/api/chat/health" in paths


check("main app imports + chat router registered", check_main)


# 8. Import migration
def check_migration():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migration_0003",
        os.path.join("backend", "alembic", "versions", "0003_chat.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "0003_chat"
    assert mod.down_revision == "0002_threat_and_investigation"
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


check("chat migration import", check_migration)


# 9. Check alembic env imports chat models
def check_alembic_env():
    content = open(os.path.join("backend", "alembic", "env.py"), encoding="utf-8").read()
    assert "import app.chat.models" in content


check("alembic env imports chat models", check_alembic_env)


if errors:
    print(f"\n{len(errors)} validation error(s).")
    sys.exit(1)
print("\nAll Phase 5 chat module validations passed.")
