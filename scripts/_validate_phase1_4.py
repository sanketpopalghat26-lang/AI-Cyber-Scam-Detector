"""Validate syntax of all Phase 1-4 module files."""
import ast
import sys

FILES = [
    "backend/app/main.py",
    "backend/app/core/config.py",
    "backend/app/core/token_store.py",
    "backend/app/threat_intelligence/__init__.py",
    "backend/app/threat_intelligence/config.py",
    "backend/app/threat_intelligence/models.py",
    "backend/app/threat_intelligence/schemas.py",
    "backend/app/threat_intelligence/providers.py",
    "backend/app/threat_intelligence/service.py",
    "backend/app/threat_intelligence/router.py",
    "backend/app/explainability/__init__.py",
    "backend/app/explainability/config.py",
    "backend/app/explainability/schemas.py",
    "backend/app/explainability/service.py",
    "backend/app/explainability/router.py",
    "backend/app/investigation/__init__.py",
    "backend/app/investigation/config.py",
    "backend/app/investigation/models.py",
    "backend/app/investigation/schemas.py",
    "backend/app/investigation/service.py",
    "backend/app/investigation/router.py",
    "backend/app/monitoring/__init__.py",
    "backend/app/monitoring/config.py",
    "backend/app/monitoring/schemas.py",
    "backend/app/monitoring/service.py",
    "backend/app/monitoring/router.py",
]

ok = True
for f in FILES:
    try:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read())
        print(f"[OK] {f}")
    except SyntaxError as e:
        ok = False
        print(f"[FAIL] {f}: {e}")

print("\nRESULT:", "ALL OK" if ok else "ERRORS FOUND")
sys.exit(0 if ok else 1)
