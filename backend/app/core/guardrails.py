"""
Enterprise AI Guardrails
==========================
Security guardrails for LLM-powered features (chat assistant, explanations).

Implements:
- Prompt injection detection
- Jailbreak detection
- Input validation (length, encoding, content)
- Output validation (dangerous content, hallucination heuristics)
- Risk scoring with confidence
- AI decision audit logging

Follows OWASP LLM Top 10 and NIST AI RMF mitigations. Pure stdlib so it can
be imported anywhere without adding runtime dependencies.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

# =============================================================================
# Threat signature catalogs
# =============================================================================

# Directive-injection / prompt-override attempts
PROMPT_INJECTION_PATTERNS: list[tuple[str, str]] = [
    ("ignore-previous", r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|messages|context|rules)"),
    ("ignore-instructions", r"ignore\s+(all\s+)?(instructions|prompts|rules|guidelines)"),
    ("new-instructions", r"(you\s+are|act\s+as|pretend)\s+(now\s+)?\("),
    ("override", r"(override|disregard|forget|forget\s+all|bypass)\s+(the\s+)?(instructions|prompts|rules|system|guidelines)"),
    ("reveal-prompt", r"(what\s+is|show|reveal|print|echo)\s+(your|the)\s+(system\s+)?prompt"),
    ("reveal-instructions", r"(reveal|show|print).{0,20}(instructions|prompt|system\s+message)"),
    ("role-play-admin", r"(assume|you\s+are)\s+(the\s+)?(admin|developer|system|superuser|god)\s+(now\s+)?(mode|role)"),
    ("delimiter-trick", r"(<\|?(system|user|assistant)\|?>|<\/?(system|user|assistant)>|\[(system|user)\])"),
]

# Jailbreak / DAN-style attempts
JAILBREAK_PATTERNS: list[tuple[str, str]] = [
    ("dan", r"\b(dan|do\s+anything\s+now|jailbreak)\b"),
    ("no-restrictions", r"(no\s+restrictions|unrestricted\s+mode|no\s+rules|without\s+rules|no\s+limitations)"),
    ("security-bypass", r"(bypass|circumvent|evade|disable).{0,30}(security|filter|safety|guardrail|moderation|policy)"),
    ("too-many-tokens", r"(pretend|imagine).{0,30}(you\s+have\s+no|without|bypass)"),
    ("sudowudo", r"\b(sudo|root)\b.{0,20}(mode|access|prompt)"),
    ("obfuscated", r"(b\s*y\s*p\s*a\s*s\s*s|d\s*a\s*n\s*|\bp\s*o\s*v\s*e\s*r\s*t\s*y)"),
]

# Content that the model should never be instructed to produce
DANGEROUS_OUTPUT_PATTERNS: list[tuple[str, str]] = [
    ("malware", r"(malware|ransomware|keylogger|trojan)\b.{0,60}(code|script|source|write|create|compile)"),
    ("exploit", r"(exploit|payload|shellcode|buffer\s+overflow).{0,40}(code|write|create|generate)"),
    ("credential-theft", r"(steal|harvest|phish).{0,30}(credential|password|bank\s+detail|card\s+number)"),
    ("pii-spill", r"\b(ssn|social\s+security\s+number|passport\s+number|national\s+id)\b"),
    ("illegal", r"(how\s+to\s+build\s+a\s+bomb|make\s+a\s+bomb|synthesize\s+illicit)"),
]

# Hallucination / unsupported-claim heuristics
UNSUPPORTED_CLAIM_PATTERNS: list[tuple[str, str]] = [
    ("absolute", r"\b(always|never|every|guaranteed|100%)\b"),
    ("unsourced-stats", r"\b\d{2,3}%?\b.{0,20}(of\s+(users|people|attacks|scams))"),
]


def _compile(pattern_list: list[tuple[str, str]]) -> list[tuple[str, re.Pattern]]:
    """Compile regex patterns, skipping invalid ones."""
    compiled: list[tuple[str, re.Pattern]] = []
    for name, pattern in pattern_list:
        try:
            compiled.append((name, re.compile(pattern, re.IGNORECASE)))
        except re.error:
            logger.warning(f"Invalid guardrail regex for '{name}'")
    return compiled


_INJECTION_RE = _compile(PROMPT_INJECTION_PATTERNS)
_JAILBREAK_RE = _compile(JAILBREAK_PATTERNS)
_DANGEROUS_OUTPUT_RE = _compile(DANGEROUS_OUTPUT_PATTERNS)
_UNSUPPORTED_RE = _compile(UNSUPPORTED_CLAIM_PATTERNS)

# =============================================================================
# Result models
# =============================================================================


@dataclass
class GuardrailFinding:
    """A single detected threat signal."""

    category: str
    pattern_name: str
    severity: str  # low | medium | high | critical
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "pattern": self.pattern_name,
            "severity": self.severity,
            "snippet": self.snippet[:200],
        }


@dataclass
class GuardrailResult:
    """Result of a guardrail evaluation."""

    allowed: bool
    risk_score: float  # 0.0 (benign) .. 1.0 (malicious)
    confidence: float  # 0.0 .. 1.0
    decision: str  # allow | reject | review
    findings: list[GuardrailFinding] = field(default_factory=list)
    reason: str = ""
    input_hash: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "risk_score": round(self.risk_score, 4),
            "confidence": round(self.confidence, 3),
            "decision": self.decision,
            "findings": [f.to_dict() for f in self.findings],
            "reason": self.reason,
            "input_hash": self.input_hash,
            "evaluated_at": self.evaluated_at,
        }


_SEVERITY_WEIGHT = {"low": 0.2, "medium": 0.4, "high": 0.6, "critical": 0.85}


def _classify(risk_score: float) -> tuple[bool, str]:
    """Map a risk score to a decision and allowed flag."""
    if risk_score >= 0.7:
        return False, "reject"
    if risk_score >= 0.4:
        return False, "review"
    return True, "allow"


def _severity_for(category: str, pattern_name: str) -> str:
    """Derive a severity for a finding based on its category."""
    if category == "prompt_injection":
        return "high"
    if category == "jailbreak":
        return "critical"
    if category == "dangerous_output":
        return "critical"
    return "medium"


# =============================================================================
# Guardrail engine
# =============================================================================


class AIGuardrails:
    """Stateless guardrail evaluation engine."""

    def __init__(
        self,
        max_input_chars: int = 20000,
        max_output_chars: int = 20000,
        reject_threshold: float = 0.7,
        review_threshold: float = 0.4,
    ) -> None:
        self.max_input_chars = max_input_chars
        self.max_output_chars = max_output_chars
        self.reject_threshold = reject_threshold
        self.review_threshold = review_threshold

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------
    def validate_input(self, text: str) -> tuple[bool, str]:
        """Perform structural input validation (length, encoding, control chars)."""
        if not text or not text.strip():
            return False, "Input is empty"
        if len(text) > self.max_input_chars:
            return False, f"Input exceeds maximum length of {self.max_input_chars} characters"
        # Reject binary control characters (except common whitespace)
        control = [c for c in text if ord(c) < 32 and c not in "\n\r\t"]
        if control:
            return False, "Input contains disallowed control characters"
        return True, "Input valid"

    # ------------------------------------------------------------------
    # Prompt injection & jailbreak detection
    # ------------------------------------------------------------------
    def detect_threat(self, text: str) -> list[GuardrailFinding]:
        """Detect prompt injection and jailbreak signals in input text."""
        findings: list[GuardrailFinding] = []
        for name, pattern in _INJECTION_RE:
            m = pattern.search(text)
            if m:
                findings.append(
                    GuardrailFinding(
                        category="prompt_injection",
                        pattern_name=name,
                        severity="high",
                        snippet=m.group(0),
                    )
                )
        for name, pattern in _JAILBREAK_RE:
            m = pattern.search(text)
            if m:
                findings.append(
                    GuardrailFinding(
                        category="jailbreak",
                        pattern_name=name,
                        severity="critical",
                        snippet=m.group(0),
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------
    def validate_output(self, output: str) -> list[GuardrailFinding]:
        """Validate model output for dangerous content or unsupported claims."""
        findings: list[GuardrailFinding] = []
        if not output:
            return findings
        if len(output) > self.max_output_chars:
            findings.append(
                GuardrailFinding(
                    category="output_length",
                    pattern_name="too_long",
                    severity="low",
                    snippet=output[:80],
                )
            )
        for name, pattern in _DANGEROUS_OUTPUT_RE:
            m = pattern.search(output)
            if m:
                findings.append(
                    GuardrailFinding(
                        category="dangerous_output",
                        pattern_name=name,
                        severity="critical",
                        snippet=m.group(0),
                    )
                )
        for name, pattern in _UNSUPPORTED_RE:
            m = pattern.search(output)
            if m:
                findings.append(
                    GuardrailFinding(
                        category="unsupported_claim",
                        pattern_name=name,
                        severity="medium",
                        snippet=m.group(0),
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Risk scoring
    # ------------------------------------------------------------------
    def _score(self, findings: list[GuardrailFinding]) -> float:
        """Convert findings into a weighted risk score in [0, 1]."""
        if not findings:
            return 0.0
        raw = sum(_SEVERITY_WEIGHT.get(f.severity, 0.2) for f in findings)
        # Use raw weights directly (saturated at 1.0) so a single high finding
        # (0.6) lands clearly in the "review" band (>= 0.4) and a single
        # critical finding (0.85) triggers "reject" (>= 0.7). Avoids
        # floating-point boundary issues from scaling.
        return round(min(1.0, raw), 4)

    def _confidence(self, findings: list[GuardrailFinding]) -> float:
        """Estimate detection confidence from number/severity of findings."""
        if not findings:
            return 0.9
        total = sum(_SEVERITY_WEIGHT.get(f.severity, 0.2) for f in findings)
        return min(0.99, 0.5 + total)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Combined evaluation
    # ------------------------------------------------------------------
    def evaluate_input(self, text: str) -> GuardrailResult:
        """Evaluate user-supplied input through the guardrail pipeline."""
        valid, reason = self.validate_input(text)
        if not valid:
            finding = GuardrailFinding(
                category="input_validation",
                pattern_name="invalid_input",
                severity="medium",
                snippet=reason,
            )
            return GuardrailResult(
                allowed=False,
                risk_score=1.0,
                confidence=0.99,
                decision="reject",
                findings=[finding],
                reason=reason,
                input_hash=self._hash(text),
            )

        findings = self.detect_threat(text)
        risk = self._score(findings)
        confidence = self._confidence(findings)
        allowed, decision = _classify(risk)

        if not findings:
            reason = "No prompt-injection or jailbreak indicators detected."
        elif allowed:
            reason = "Low-risk signals detected; input allowed for review."
        else:
            reason = (
                f"Blocked: {len(findings)} threat signal(s) detected "
                f"({', '.join(f.pattern_name for f in findings[:3])})."
            )

        return GuardrailResult(
            allowed=allowed,
            risk_score=risk,
            confidence=confidence,
            decision=decision,
            findings=findings,
            reason=reason,
            input_hash=self._hash(text),
        )

    def evaluate_output(self, output: str) -> GuardrailResult:
        """Evaluate model-generated output before returning to the user."""
        findings = self.validate_output(output)
        risk = self._score(findings)
        confidence = self._confidence(findings)
        allowed, decision = _classify(risk)

        if not findings:
            reason = "Output passed content-safety validation."
        else:
            reason = (
                f"Output flagged: {len(findings)} signal(s) "
                f"({', '.join(f.pattern_name for f in findings[:3])})."
            )

        return GuardrailResult(
            allowed=allowed,
            risk_score=risk,
            confidence=confidence,
            decision=decision,
            findings=findings,
            reason=reason,
            input_hash=self._hash(output),
        )

    def audit(self, result: GuardrailResult, context: dict[str, Any]) -> None:
        """Write an AI decision audit log entry."""
        from .audit import get_audit_logger

        get_audit_logger().log(
            action="ai.guardrail",
            actor=str(context.get("actor", "system")),
            resource=context.get("resource", "llm"),
            result="blocked" if not result.allowed else "allowed",
            details={
                "decision": result.decision,
                "risk_score": round(result.risk_score, 4),
                "confidence": round(result.confidence, 3),
                "findings": [f.to_dict() for f in result.findings],
                "input_hash": result.input_hash,
                "reason": result.reason,
            },
            severity=(
                "critical"
                if result.risk_score >= self.reject_threshold
                else "warning"
                if result.risk_score >= self.review_threshold
                else "info"
            ),
        )


# Singleton for application-wide use
_guardrails_instance: AIGuardrails | None = None


def get_guardrails() -> AIGuardrails:
    """Get the global guardrails engine instance."""
    global _guardrails_instance
    if _guardrails_instance is None:
        _guardrails_instance = AIGuardrails()
    return _guardrails_instance
