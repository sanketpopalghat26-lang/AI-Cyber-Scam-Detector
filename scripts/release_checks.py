"""Release quality gate checks.

Authoritative scan for issues that would emit warnings under modern Python:
1. Invalid escape sequences in string literals (compiles each module, catches
   SyntaxWarning) - the only reliable way to detect real problems.
2. TODO/FIXME/XXX/HACK placeholder comments.
3. Deprecated APIs that are under our control.

Exit code 0 = all clean, 1 = real issues found.
"""
import pathlib
import re
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Paths that are not part of the shipped source (would create noise).
EXCLUDE_SUBSTR = (
    ".venv",
    "node_modules",
    "mlruns",
    "__pycache__",
    "models/exports",
    ".git",
    ".pytest_cache",
)

real_warning_files = []
placeholder_files = []
# Canary patterns for deprecated APIs we intentionally control.
canary_patterns = {
    "datetime.utcnow()": "datetime.utcnow() is deprecated (use timezone-aware UTC)",
    "select_dtypes(include=\"object\")": "pandas select_dtypes('object') deprecation",
    "select_dtypes(include=['object'])": "pandas select_dtypes('object') deprecation",
    "pkg_resources": "pkg_resources is deprecated (use importlib.resources)",
}


def iter_py_files():
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDE_SUBSTR for part in rel.parts):
            continue
        if rel.name == "release_checks.py":  # never scan ourselves
            continue
        yield p, rel


# --- 1. Authoritative invalid-escape detection via compile ----------------------
def check_escapes(path: pathlib.Path, rel: pathlib.Path) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            compile(source, str(rel), "exec")
        except SyntaxError as exc:
            real_warning_files.append(f"{rel}: {exc}")
            return
        for w in caught:
            if issubclass(w.category, SyntaxWarning):
                lineno = getattr(w, "lineno", "?")
                msg = str(w.message)
                real_warning_files.append(f"{rel}:{lineno}: {msg}")


# --- 2. Placeholders -------------------------------------------------------------
def check_placeholders(path: pathlib.Path, rel: pathlib.Path) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for i, line in enumerate(source.splitlines(), 1):
        if re.search(r"#\s*(TODO|FIXME|XXX|HACK)\b", line, re.IGNORECASE):
            placeholder_files.append(f"{rel}:{i}: {line.strip()[:90]}")


# --- 3. Deprecated APIs (canary strings only - exact matches) -------------------
def check_deprecated(path: pathlib.Path, rel: pathlib.Path) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for needle, label in canary_patterns.items():
        start = 0
        while True:
            idx = source.find(needle, start)
            if idx == -1:
                break
            lines_before = source.count("\n", 0, idx) + 1
            real_warning_files.append(f"{rel}:{lines_before}: {label}")
            start = idx + 1


for p, rel in iter_py_files():
    check_escapes(p, rel)
    check_placeholders(p, rel)
    check_deprecated(p, rel)

# --- Report -----------------------------------------------------------------------
issues = 0
if real_warning_files:
    issues += 1
    print(f"REAL ISSUES ({len(real_warning_files)}):")
    for line in real_warning_files:
        print(f"  {line}")
else:
    print("OK: no invalid escape sequences or deprecated API usages")

if placeholder_files:
    issues += 1
    print(f"PLACEHOLDER COMMENTS: {len(placeholder_files)}")
    for line in placeholder_files[:30]:
        print(f"  {line}")
else:
    print("OK: no TODO/FIXME/XXX/HACK placeholders")

sys.exit(0 if issues == 0 else 1)
