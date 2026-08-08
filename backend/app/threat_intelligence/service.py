"""
Threat Intelligence Service
============================
Core service layer implementing the threat intelligence business logic.

Features:
- IOC database management (CRUD, search, stats)
- Multi-provider threat analysis with aggregation
- Threat scoring engine with weighted calculation
- IOC auto-update scheduler
- Caching with Redis
- Full observability (metrics, logging, health checks)
- Audit logging for compliance
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlmodel import Session, and_, func, or_, select

from ..core.audit import get_audit_logger
from ..core.db import engine
from ..core.observability import (
    Counter as PromCounter,
)
from ..core.observability import (
    Gauge as PromGauge,
)
from ..core.observability import (
    Histogram as PromHistogram,
)
from .config import ThreatIntelConfig
from .models import (
    IOCStatus,
    IOCType,
    RiskLevel,
    ThreatAnalysis,
    ThreatCategory,
    ThreatFeed,
    ThreatFeedSource,
    ThreatIOC,
    ThreatRiskScore,
    ThreatTimelineEntry,
)
from .providers import (
    ProviderRegistry,
    _auto_detect_type,
    _categorize_threat,
)
from .schemas import (
    IOCEntry,
    ProviderResult,
    ThreatAnalyzeResponse,
    ThreatSearchResponse,
    ThreatStatsResponse,
)

# =============================================================================
# Prometheus Metrics for Threat Intelligence
# =============================================================================

threat_analyses_total = PromCounter(
    "threat_analyses_total",
    "Total number of threat analyses performed",
    ["result", "provider"],
)

threat_analysis_duration = PromHistogram(
    "threat_analysis_duration_seconds",
    "Duration of threat analysis",
    ["provider"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

threat_iocs_total = PromGauge(
    "threat_iocs_total",
    "Total number of IOCs in database",
    ["type", "status"],
)

threat_feeds_active = PromGauge(
    "threat_feeds_active",
    "Number of active threat feeds",
)

threat_feed_updates_total = PromCounter(
    "threat_feed_updates_total",
    "Total number of feed updates",
    ["feed", "status"],
)


# =============================================================================
# Threat Intelligence Service
# =============================================================================


class ThreatIntelligenceService:
    """
    Core service for threat intelligence operations.

    Implements:
    - IOC database management
    - Multi-provider threat analysis with scoring
    - Feed auto-update scheduling
    - Caching and observability
    """

    def __init__(self, config: ThreatIntelConfig | None = None):
        self.config = config or ThreatIntelConfig.from_env()
        self.providers = ProviderRegistry(self.config)
        self._update_task: asyncio.Task | None = None

    # =========================================================================
    # IOC Database Operations
    # =========================================================================

    def search_iocs(
        self,
        query: str,
        ioc_type: IOCType | None = None,
        threat_category: ThreatCategory | None = None,
        risk_level: RiskLevel | None = None,
        status: IOCStatus | None = None,
        source: ThreatFeedSource | None = None,
        limit: int = 50,
        offset: int = 0,
        include_expired: bool = False,
    ) -> ThreatSearchResponse:
        """
        Search the IOC database with filters.
        Supports full-text search, type filtering, and pagination.
        """
        start_time = time.time()

        with Session(engine) as session:
            # Base query
            conditions = [
                or_(
                    ThreatIOC.ioc_value.ilike(f"%{query}%"),
                    ThreatIOC.tags.ilike(f"%{query}%"),
                    ThreatIOC.notes.ilike(f"%{query}%"),
                    ThreatIOC.asn_org.ilike(f"%{query}%"),
                    ThreatIOC.isp.ilike(f"%{query}%"),
                )
            ]

            # Apply filters
            if ioc_type:
                conditions.append(ThreatIOC.ioc_type == ioc_type)
            if threat_category:
                conditions.append(ThreatIOC.threat_category == threat_category)
            if risk_level:
                risk_threshold = self._risk_level_to_score(risk_level)
                conditions.append(ThreatIOC.risk_score >= risk_threshold)
            if status:
                conditions.append(ThreatIOC.status == status)
            if source:
                conditions.append(ThreatIOC.source == source)
            if not include_expired:
                conditions.append(ThreatIOC.status != IOCStatus.EXPIRED)

            # Count total
            count_query = select(func.count()).select_from(ThreatIOC).where(and_(*conditions))
            total = session.exec(count_query).one()

            # Fetch results
            fetch_query = (
                select(ThreatIOC)
                .where(and_(*conditions))
                .order_by(ThreatIOC.risk_score.desc(), ThreatIOC.last_seen.desc())
                .offset(offset)
                .limit(limit)
            )
            results = session.exec(fetch_query).all()

        search_time_ms = (time.time() - start_time) * 1000

        return ThreatSearchResponse(
            total=total,
            results=[IOCEntry.model_validate(ioc) for ioc in results],
            query=query,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
            search_time_ms=round(search_time_ms, 2),
        )

    def get_ioc_stats(self) -> ThreatStatsResponse:
        """
        Get comprehensive statistics about the IOC database.
        Results are cached for performance.
        """
        with Session(engine) as session:
            # Total counts
            total_iocs = session.exec(
                select(func.count()).select_from(ThreatIOC)
            ).one()

            active_iocs = session.exec(
                select(func.count())
                .select_from(ThreatIOC)
                .where(ThreatIOC.status == IOCStatus.ACTIVE)
            ).one()

            # By type
            type_query = session.exec(
                select(ThreatIOC.ioc_type, func.count())
                .group_by(ThreatIOC.ioc_type)
            ).all()
            by_type = {str(t): c for t, c in type_query}

            # By category
            category_query = session.exec(
                select(ThreatIOC.threat_category, func.count())
                .group_by(ThreatIOC.threat_category)
            ).all()
            by_category = {str(c): count for c, count in category_query}

            # By risk level
            risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
            risk_query = session.exec(
                select(ThreatIOC.risk_score)
                .where(ThreatIOC.status == IOCStatus.ACTIVE)
            ).all()
            for score in risk_query:
                if score >= 0.8:
                    risk_counts["critical"] += 1
                elif score >= 0.6:
                    risk_counts["high"] += 1
                elif score >= 0.4:
                    risk_counts["medium"] += 1
                elif score >= 0.2:
                    risk_counts["low"] += 1
                else:
                    risk_counts["info"] += 1

            # By source
            source_query = session.exec(
                select(ThreatIOC.source, func.count())
                .group_by(ThreatIOC.source)
            ).all()
            by_source = {str(s): c for s, c in source_query}

            # Total analyses
            total_analyses = session.exec(
                select(func.count()).select_from(ThreatAnalysis)
            ).one()

            # Malicious percentage
            malicious_count = session.exec(
                select(func.count())
                .select_from(ThreatIOC)
                .where(ThreatIOC.risk_score >= 0.6)
            ).one()
            malicious_percentage = (
                round((malicious_count / max(total_iocs, 1)) * 100, 2)
            )

            # Feed status
            feed_query = session.exec(select(ThreatFeed)).all()
            feed_status = [
                {
                    "id": f.id,
                    "source": f.source.value,
                    "name": f.name,
                    "enabled": f.enabled,
                    "status": f.status,
                    "last_update": f.last_update.isoformat() if f.last_update else None,
                    "total_iocs": f.total_iocs_imported,
                }
                for f in feed_query
            ]

            # Top countries
            country_query = session.exec(
                select(ThreatIOC.country_code, func.count())
                .where(ThreatIOC.country_code.isnot(None))
                .group_by(ThreatIOC.country_code)
                .order_by(func.count().desc())
                .limit(10)
            ).all()
            top_countries = [
                {"country": c, "count": count} for c, count in country_query
            ]

            # Top ASNs
            asn_query = session.exec(
                select(ThreatIOC.asn_org, func.count())
                .where(ThreatIOC.asn_org.isnot(None))
                .group_by(ThreatIOC.asn_org)
                .order_by(func.count().desc())
                .limit(10)
            ).all()
            top_asns = [
                {"asn_org": a, "count": count} for a, count in asn_query
            ]

            # Recent timeline activity
            timeline_query = session.exec(
                select(ThreatTimelineEntry)
                .order_by(ThreatTimelineEntry.created_at.desc())
                .limit(20)
            ).all()
            recent_activity = [
                {
                    "id": t.id,
                    "event_type": t.event_type,
                    "description": t.description[:100],
                    "severity": t.severity.value,
                    "created_at": t.created_at.isoformat(),
                }
                for t in timeline_query
            ]

        return ThreatStatsResponse(
            total_iocs=total_iocs,
            active_iocs=active_iocs,
            by_type=by_type,
            by_category=by_category,
            by_risk_level=risk_counts,
            by_source=by_source,
            total_analyses=total_analyses,
            malicious_percentage=malicious_percentage,
            feed_status=feed_status,
            top_countries=top_countries,
            top_asns=top_asns,
            recent_activity=recent_activity,
            last_updated=datetime.now(UTC).isoformat(),
        )

    # =========================================================================
    # Threat Analysis
    # =========================================================================

    async def analyze(
        self,
        value: str,
        value_type: IOCType | None = None,
        source: str = "api",
        user_id: int | None = None,
        **provider_flags: bool,
    ) -> ThreatAnalyzeResponse:
        """
        Perform a full threat analysis against all enabled providers.

        Args:
            value: The IOC value to analyze
            value_type: IOC type (auto-detected if not provided)
            source: Source of the analysis request
            user_id: Authenticated user ID (optional)

        Returns:
            Comprehensive analysis response with all provider results
        """
        start_time = time.time()

        # Auto-detect type if not provided
        if value_type is None:
            value_type = _auto_detect_type(value)

        # Run all provider checks
        providers_to_check = self._get_providers_to_check(**provider_flags)
        provider_results = await self._run_provider_checks(
            value, value_type, providers_to_check
        )

        # Calculate aggregate scores
        total_sources = len(provider_results)
        successful_results = [r for r in provider_results if r.get("success")]
        malicious_results = [r for r in provider_results if r.get("malicious")]
        positive_count = len(malicious_results)

        # Weighted risk score calculation
        risk_score = self._calculate_risk_score(provider_results)
        risk_level = self._score_to_risk_level(risk_score)
        confidence = self._calculate_confidence(provider_results)

        # Determine threat category
        threat_category = _categorize_threat(provider_results)

        # Build explanation
        explanation = self._build_explanation(
            value, value_type, risk_score, positive_count, total_sources
        )

        # Extract tags
        tags = self._extract_tags(provider_results)

        # Persist analysis and IOC
        analysis_id = await self._persist_analysis(
            value=value,
            value_type=value_type,
            risk_score=risk_score,
            risk_level=risk_level,
            threat_category=threat_category,
            is_malicious=positive_count > 0,
            confidence=confidence,
            provider_results=provider_results,
            source=source,
            user_id=user_id,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

        # Record metrics
        threat_analyses_total.labels(
            result="malicious" if positive_count > 0 else "clean",
            provider="aggregate",
        ).inc()

        # Audit log
        get_audit_logger().log(
            action="threat_intel.analyze",
            actor=str(user_id) if user_id else "anonymous",
            resource="threat_analysis",
            resource_id=str(analysis_id),
            result="success",
            details={
                "value": value[:100],
                "value_type": value_type.value,
                "risk_score": risk_score,
                "risk_level": risk_level.value,
                "positive_detections": positive_count,
                "sources_checked": total_sources,
            },
        )

        # Extract geographic and network data from provider results
        geoip = self._extract_geoip(provider_results)
        dns_data = self._extract_dns(provider_results)
        whois_data = self._extract_whois(provider_results)
        asn_data = self._extract_asn(provider_results)

        return ThreatAnalyzeResponse(
            id=analysis_id,
            value=value,
            value_type=value_type,
            is_malicious=positive_count > 0,
            risk_score=round(risk_score, 4),
            risk_level=risk_level,
            threat_category=threat_category,
            confidence=round(confidence, 4),
            sources_checked=total_sources,
            positive_detections=positive_count,
            total_detections=sum(
                r.get("details", {}).get("total_reports", 0)
                if r.get("details")
                else 0
                for r in successful_results
            ),
            provider_results=[
                ProviderResult(**r) for r in provider_results
            ] if provider_results else [],
            geoip=geoip,
            dns=dns_data,
            whois=whois_data,
            asn=asn_data,
            explanation=explanation,
            tags=tags,
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
            created_at=datetime.now(UTC).isoformat(),
        )

    def _get_providers_to_check(self, **flags: bool) -> list[str]:
        """Get list of providers to check based on feature flags."""
        provider_map = {
            "check_virustotal": "virustotal",
            "check_abuseipdb": "abuseipdb",
            "check_phishtank": "phishtank",
            "check_openphish": "openphish",
            "check_alienvault": "alienvault",
            "check_dns": "dns",
            "check_whois": "whois",
            "check_geoip": "geoip",
            "check_asn": "asn",
        }

        # Default to all enabled providers if no flags specified
        if not any(flags.values()):
            return self.config.get_enabled_providers()

        enabled = []
        for flag, provider_name in provider_map.items():
            if flags.get(flag, True):
                enabled.append(provider_name)
        return enabled

    async def _run_provider_checks(
        self, value: str, value_type: IOCType, provider_names: list[str]
    ) -> list[dict[str, Any]]:
        """Run checks against multiple providers concurrently."""
        results = []
        tasks = []

        for name in provider_names:
            provider = self.providers.get_provider(name)
            if provider:
                task = self._check_single_provider(provider, value, value_type)
                tasks.append(task)

        if tasks:
            provider_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in provider_results:
                if isinstance(result, Exception):
                    results.append({
                        "provider": "unknown",
                        "success": False,
                        "malicious": False,
                        "confidence": 0.0,
                        "details": None,
                        "error": str(result)[:200],
                        "response_time_ms": 0.0,
                    })
                else:
                    results.append(result)

        return results

    async def _check_single_provider(
        self, provider, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        """Check a single provider with timing and error handling."""
        start = time.time()
        try:
            result = await provider.analyze(value, value_type)
            duration = (time.time() - start) * 1000

            # Record metrics
            threat_analysis_duration.labels(
                provider=provider.name
            ).observe(duration / 1000.0)

            threat_analyses_total.labels(
                result="malicious" if result.get("malicious") else "clean",
                provider=provider.name,
            ).inc()

            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Provider {provider.name} check failed: {e}")
            return {
                "provider": provider.name,
                "success": False,
                "malicious": False,
                "confidence": 0.0,
                "details": None,
                "error": str(e)[:200],
                "response_time_ms": duration,
            }

    # =========================================================================
    # Scoring Engine
    # =========================================================================

    def _calculate_risk_score(
        self, provider_results: list[dict[str, Any]]
    ) -> float:
        """
        Calculate weighted composite risk score from all provider results.

        Uses configurable weights for each provider type.
        """
        weights = self.config.threat_score_weights
        total_weight = 0.0
        weighted_score = 0.0

        for result in provider_results:
            provider_name = result.get("provider", "")
            weight = weights.get(provider_name, 0.1)
            confidence = result.get("confidence", 0.0)
            malicious = result.get("malicious", False)

            provider_score = confidence if malicious else 0.0
            weighted_score += provider_score * weight
            total_weight += weight

        return weighted_score / max(total_weight, 0.01)

    def _calculate_confidence(
        self, provider_results: list[dict[str, Any]]
    ) -> float:
        """Calculate overall confidence based on provider agreement."""
        successful = [r for r in provider_results if r.get("success")]
        if not successful:
            return 0.0

        malicious_count = sum(1 for r in successful if r.get("malicious"))
        agreement = malicious_count / len(successful)

        # Higher confidence when more providers agree
        if agreement > 0.5:
            return min(agreement + 0.2, 1.0)
        return agreement

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert numerical risk score to risk level."""
        if score >= 0.8:
            return RiskLevel.CRITICAL
        elif score >= self.config.risk_threshold_high:
            return RiskLevel.HIGH
        elif score >= self.config.risk_threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= 0.1:
            return RiskLevel.LOW
        return RiskLevel.INFO

    def _risk_level_to_score(self, level: RiskLevel) -> float:
        """Convert risk level to minimum score threshold."""
        thresholds = {
            RiskLevel.CRITICAL: 0.8,
            RiskLevel.HIGH: 0.6,
            RiskLevel.MEDIUM: 0.4,
            RiskLevel.LOW: 0.2,
            RiskLevel.INFO: 0.0,
            RiskLevel.UNKNOWN: 0.0,
        }
        return thresholds.get(level, 0.0)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_explanation(
        self,
        value: str,
        value_type: IOCType,
        risk_score: float,
        positive_count: int,
        total_sources: int,
    ) -> str:
        """Build a human-readable explanation of the analysis."""
        if risk_score >= 0.8:
            return (
                f"Critical threat detected: {value} ({value_type.value}) shows "
                f"strong malicious indicators across {positive_count}/{total_sources} "
                f"intelligence sources. Immediate action recommended."
            )
        elif risk_score >= 0.6:
            return (
                f"High-risk indicator: {value} ({value_type.value}) flagged by "
                f"{positive_count}/{total_sources} sources. "
                f"Exercise caution and investigate further."
            )
        elif risk_score >= 0.4:
            return (
                f"Medium-risk indicator: {value} ({value_type.value}) raised "
                f"flags in {positive_count}/{total_sources} sources. "
                f"Recommend monitoring and additional verification."
            )
        elif risk_score >= 0.1:
            return (
                f"Low-risk indicator: {value} ({value_type.value}) has minor "
                f"signals from {positive_count}/{total_sources} sources. "
                f"Likely safe but keep monitoring."
            )
        return (
            f"No significant threat detected for {value} ({value_type.value}). "
            f"Checked {total_sources} intelligence sources."
        )

    def _extract_tags(
        self, provider_results: list[dict[str, Any]]
    ) -> list[str]:
        """Extract tags from provider results."""
        tags = set()
        for result in provider_results:
            details = result.get("details") or {}
            if details.get("tags"):
                tags.update(details["tags"])
            if result.get("malicious"):
                tags.add(result.get("provider", "unknown"))
        return sorted(tags)

    def _extract_geoip(
        self, provider_results: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Extract GeoIP data from provider results."""
        for result in provider_results:
            if result.get("provider") == "geoip_analysis" and result.get("success"):
                return result.get("details")
        return None

    def _extract_dns(
        self, provider_results: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Extract DNS data from provider results."""
        for result in provider_results:
            if result.get("provider") == "dns_analysis" and result.get("success"):
                return result.get("details")
        return None

    def _extract_whois(
        self, provider_results: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Extract WHOIS data from provider results."""
        for result in provider_results:
            if result.get("provider") == "whois_lookup" and result.get("success"):
                return result.get("details")
        return None

    def _extract_asn(
        self, provider_results: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Extract ASN data from provider results."""
        for result in provider_results:
            if result.get("provider") == "asn_lookup" and result.get("success"):
                return result.get("details")
        return None

    async def _persist_analysis(
        self,
        value: str,
        value_type: IOCType,
        risk_score: float,
        risk_level: RiskLevel,
        threat_category: ThreatCategory,
        is_malicious: bool,
        confidence: float,
        provider_results: list[dict[str, Any]],
        source: str,
        user_id: int | None,
        processing_time_ms: float,
    ) -> int:
        """Persist analysis results to database."""
        try:
            with Session(engine) as session:
                # Create the analysis record
                analysis = ThreatAnalysis(
                    query_value=value,
                    query_type=value_type,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    threat_category=threat_category,
                    is_malicious=is_malicious,
                    confidence=confidence,
                    sources_checked=len(provider_results),
                    positive_detections=sum(
                        1 for r in provider_results if r.get("malicious")
                    ),
                    total_detections=len(provider_results),
                    provider_results={
                        r["provider"]: r for r in provider_results
                    },
                    source=source,
                    user_id=user_id,
                    processing_time_ms=processing_time_ms,
                )
                session.add(analysis)
                session.flush()

                # Create or update IOC
                existing = session.exec(
                    select(ThreatIOC).where(
                        ThreatIOC.ioc_value == value,
                        ThreatIOC.ioc_type == value_type,
                    )
                ).first()

                if existing:
                    existing.last_seen = datetime.now(UTC)
                    existing.risk_score = max(existing.risk_score, risk_score)
                    existing.confidence = max(existing.confidence, confidence)
                    if existing.threat_category == ThreatCategory.UNKNOWN:
                        existing.threat_category = threat_category
                else:
                    # Extract additional data from provider results
                    geoip_data = self._extract_geoip(provider_results)
                    whois_data = self._extract_whois(provider_results)

                    ioc = ThreatIOC(
                        ioc_value=value,
                        ioc_type=value_type,
                        threat_category=threat_category,
                        status=IOCStatus.ACTIVE,
                        confidence=confidence,
                        severity=risk_score,
                        risk_score=risk_score,
                        source=self._detect_source_from_providers(provider_results),
                        country_code=geoip_data.get("country_code") if geoip_data else None,
                        asn_org=asn_data.get("asn_org") if (asn_data := self._extract_asn(provider_results)) else None,
                        domain_registrar=whois_data.get("registrar") if whois_data else None,
                        tags=",".join(self._extract_tags(provider_results)),
                    )
                    session.add(ioc)
                    session.flush()

                    # Create timeline entry
                    timeline = ThreatTimelineEntry(
                        event_type="ioc_added",
                        description=f"New {value_type.value} IOC added: {value}",
                        severity=risk_level,
                        ioc_id=ioc.id,
                        analysis_id=analysis.id,
                    )
                    session.add(timeline)

                # Create risk score record
                risk_record = ThreatRiskScore(
                    ioc_id=existing.id if existing else ioc.id,
                    score_value=risk_score,
                    score_components={
                        r["provider"]: {
                            "malicious": r.get("malicious"),
                            "confidence": r.get("confidence"),
                        }
                        for r in provider_results
                    },
                    risk_level=risk_level,
                )
                session.add(risk_record)

                session.commit()
                return analysis.id

        except Exception as e:
            logger.error(f"Failed to persist threat analysis: {e}")
            return 0

    def _detect_source_from_providers(
        self, provider_results: list[dict[str, Any]]
    ) -> ThreatFeedSource:
        """Detect the most likely source from provider results."""
        malicious_providers = [
            r.get("provider") for r in provider_results if r.get("malicious")
        ]
        if malicious_providers:
            source_map = {
                "virustotal": ThreatFeedSource.VIRUSTOTAL,
                "abuseipdb": ThreatFeedSource.ABUSEIPDB,
                "openphish": ThreatFeedSource.OPENPHISH,
                "phishtank": ThreatFeedSource.PHISHTANK,
                "alienvault_otx": ThreatFeedSource.ALIENVAULT_OTX,
            }
            return source_map.get(
                malicious_providers[0], ThreatFeedSource.INTERNAL_ANALYSIS
            )
        return ThreatFeedSource.INTERNAL_ANALYSIS

    # =========================================================================
    # Feed Auto-Update Scheduler
    # =========================================================================

    async def start_feed_updates(self):
        """Start the auto-update scheduler for threat feeds."""
        if self._update_task is not None:
            logger.warning("Feed update task already running")
            return

        self._update_task = asyncio.create_task(self._feed_update_loop())
        logger.info("Threat feed auto-update scheduler started")

    async def stop_feed_updates(self):
        """Stop the feed update scheduler."""
        if self._update_task:
            self._update_task.cancel()
            self._update_task = None
            logger.info("Threat feed auto-update scheduler stopped")

    async def _feed_update_loop(self):
        """Main feed update loop."""
        while True:
            try:
                await self._update_all_feeds()
            except Exception as e:
                logger.error(f"Feed update cycle failed: {e}")

            await asyncio.sleep(self.config.ioc_auto_update_interval)

    async def _update_all_feeds(self):
        """Update all configured threat feeds."""
        logger.info("Starting threat feed update cycle")

        # Update OpenPhish feed
        openphish = self.providers.get_provider("openphish")
        if openphish:
            try:
                await openphish._ensure_fresh()
                threat_feed_updates_total.labels(
                    feed="openphish", status="success"
                ).inc()
            except Exception as e:
                logger.error(f"OpenPhish feed update failed: {e}")
                threat_feed_updates_total.labels(
                    feed="openphish", status="failed"
                ).inc()

        logger.info("Threat feed update cycle completed")

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Get health status of the threat intelligence module."""
        provider_health = await self.providers.health_check_all()

        return {
            "enabled": self.config.enabled,
            "configured": self.config.is_fully_configured(),
            "providers": provider_health,
            "feed_updates_running": self._update_task is not None,
        }

    async def close(self):
        """Clean up resources."""
        await self.stop_feed_updates()
        await self.providers.close_all()

    def get_provider_registry(self) -> ProviderRegistry:
        """Get the provider registry for direct access."""
        return self.providers

