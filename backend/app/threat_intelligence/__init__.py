"""
AI Threat Intelligence Center
==============================
Enterprise-grade threat intelligence module providing IOC management,
malicious IP/domain/URL detection, phishing analysis, and integration
with major threat intelligence feeds.

This module follows Clean Architecture with domain-driven design (DDD)
patterns and is fully integrated with the enterprise observability,
resilience, caching, and security frameworks.

Feature Flag: ENABLE_THREAT_INTEL (default: true)
"""

from .config import ThreatIntelConfig
from .models import (
    ThreatAnalysis,
    ThreatCategory,
    ThreatFeed,
    ThreatIOC,
    ThreatRiskScore,
    ThreatTimelineEntry,
)
from .router import router
from .schemas import (
    IOCEntry,
    ThreatAnalyzeRequest,
    ThreatAnalyzeResponse,
    ThreatFeedEntry,
    ThreatSearchParams,
    ThreatSearchResponse,
    ThreatStatsResponse,
)
from .service import ThreatIntelligenceService

__all__ = [
    "ThreatIntelConfig",
    "ThreatIOC",
    "ThreatFeed",
    "ThreatAnalysis",
    "ThreatCategory",
    "ThreatTimelineEntry",
    "ThreatRiskScore",
    "ThreatSearchParams",
    "ThreatSearchResponse",
    "ThreatStatsResponse",
    "ThreatAnalyzeRequest",
    "ThreatAnalyzeResponse",
    "IOCEntry",
    "ThreatFeedEntry",
    "ThreatIntelligenceService",
    "router",
]

