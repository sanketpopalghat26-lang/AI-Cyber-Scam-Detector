"""
Threat Intelligence Providers
==============================
Integration with external threat intelligence providers.
Each provider follows the Provider Interface for dependency injection.

Supports:
- VirusTotal (v3 API)
- AbuseIPDB (v2 API)
- OpenPhish (feed)
- PhishTank (API)
- AlienVault OTX (v1 API)
- DNS Analysis
- WHOIS Lookup
- GeoIP Analysis
- ASN Lookup
"""

import contextlib
import ipaddress
import re
import socket
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from .config import ThreatIntelConfig
from .models import IOCType, ThreatCategory

# =============================================================================
# Abstract Provider Interface
# =============================================================================


class ThreatProvider(ABC):
    """Abstract base class for all threat intelligence providers."""

    def __init__(self, config: ThreatIntelConfig):
        self.config = config
        self.name = self.__class__.__name__.lower().replace("provider", "")

    @abstractmethod
    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        """
        Analyze a value using this provider.

        Returns:
            dict with keys:
                - provider: str
                - success: bool
                - malicious: bool
                - confidence: float
                - details: dict | None
                - error: str | None
                - response_time_ms: float
        """
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check if the provider is available."""
        ...


# =============================================================================
# Helper Functions
# =============================================================================


def _auto_detect_type(value: str) -> IOCType:
    """Auto-detect IOC type from a value string."""
    value = value.strip().lower()

    # Check if it's an IP address
    try:
        ipaddress.ip_address(value)
        return IOCType.IP
    except ValueError:
        pass

    # Check if it's a URL
    if value.startswith(("http://", "https://", "ftp://")):
        return IOCType.URL

    # Check if it looks like a domain
    domain_pattern = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
    )
    if domain_pattern.match(value):
        return IOCType.DOMAIN

    # Check if it's an MD5 hash (32 hex chars)
    if re.match(r"^[a-f0-9]{32}$", value):
        return IOCType.HASH_MD5

    # Check if it's a SHA1 hash (40 hex chars)
    if re.match(r"^[a-f0-9]{40}$", value):
        return IOCType.HASH_SHA1

    # Check if it's a SHA256 hash (64 hex chars)
    if re.match(r"^[a-f0-9]{64}$", value):
        return IOCType.HASH_SHA256

    # Check if it's an email
    if "@" in value and "." in value.split("@")[-1]:
        return IOCType.EMAIL

    return IOCType.URL  # Default to URL


def _extract_domain(url_or_domain: str) -> str:
    """Extract domain from a URL or return the domain itself."""
    url = url_or_domain.strip().lower()
    if url.startswith(("http://", "https://", "ftp://")):
        parsed = urlparse(url)
        return parsed.netloc or parsed.hostname or url
    return url


def _categorize_threat(
    provider_results: list[dict[str, Any]],
) -> ThreatCategory:
    """Categorize a threat based on provider results."""
    categories = []
    for result in provider_results:
        details = result.get("details", {}) or {}
        if details.get("category"):
            categories.append(details["category"])

    # Count occurrences
    from collections import Counter
    category_counts = Counter(categories)

    if not category_counts:
        return ThreatCategory.UNKNOWN

    # Return the most common category
    return ThreatCategory(category_counts.most_common(1)[0][0])


# =============================================================================
# VirusTotal Provider
# =============================================================================


class VirusTotalProvider(ThreatProvider):
    """VirusTotal v3 API integration."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.api_key = config.virustotal_api_key
        self.base_url = config.virustotal_base_url
        self.timeout = config.virustotal_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "x-apikey": self.api_key or "",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "virustotal",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        if not self.api_key:
            result["error"] = "API key not configured"
            result["response_time_ms"] = (time.time() - start) * 1000
            return result

        try:
            client = await self._get_client()
            endpoint = self._get_endpoint(value, value_type)
            if not endpoint:
                result["error"] = f"Unsupported IOC type: {value_type}"
                result["response_time_ms"] = (time.time() - start) * 1000
                return result

            response = await client.get(endpoint)
            result["response_time_ms"] = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                attributes = data.get("data", {}).get("attributes", {})
                last_analysis = attributes.get("last_analysis_stats", {})

                malicious = last_analysis.get("malicious", 0)
                suspicious = last_analysis.get("suspicious", 0)
                total = sum(last_analysis.values()) if last_analysis else 0

                result["success"] = True
                result["malicious"] = malicious > 0
                result["confidence"] = min(
                    (malicious + suspicious * 0.5) / max(total, 1) * 2, 1.0
                )
                result["details"] = {
                    "stats": last_analysis,
                    "reputation": attributes.get("reputation", 0),
                    "harmless": last_analysis.get("harmless", 0),
                    "undetected": last_analysis.get("undetected", 0),
                    "timeout": last_analysis.get("timeout", 0),
                }
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"

        except httpx.TimeoutException:
            result["error"] = "Request timed out"
            result["response_time_ms"] = (time.time() - start) * 1000
        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"VirusTotal analysis failed: {e}")

        return result

    def _get_endpoint(self, value: str, value_type: IOCType) -> str | None:
        """Get the appropriate API endpoint for the IOC type."""
        endpoints = {
            IOCType.IP: f"/ip_addresses/{value}",
            IOCType.DOMAIN: f"/domains/{value}",
            IOCType.URL: f"/urls/{_encode_url(value)}",
            IOCType.HASH_MD5: f"/files/{value}",
            IOCType.HASH_SHA1: f"/files/{value}",
            IOCType.HASH_SHA256: f"/files/{value}",
        }
        return endpoints.get(value_type)

    async def health_check(self) -> dict[str, Any]:
        if not self.api_key:
            return {"provider": "virustotal", "status": "not_configured"}
        try:
            client = await self._get_client()
            response = await client.get("/ip_addresses/8.8.8.8")
            return {
                "provider": "virustotal",
                "status": "healthy" if response.status_code == 200 else "unhealthy",
            }
        except Exception as e:
            return {"provider": "virustotal", "status": "unhealthy", "error": str(e)[:100]}

    async def close(self):
        if self._client:
            await self._client.aclose()


def _encode_url(url: str) -> str:
    """Base64 encode a URL for the VirusTotal API."""
    import base64
    return base64.urlsafe_b64encode(url.encode()).decode().strip("=")


# =============================================================================
# AbuseIPDB Provider
# =============================================================================


class AbuseIPDBProvider(ThreatProvider):
    """AbuseIPDB v2 API integration for IP address reputation."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.api_key = config.abuseipdb_api_key
        self.base_url = config.abuseipdb_base_url
        self.timeout = config.abuseipdb_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Key": self.api_key or "",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "abuseipdb",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        if not self.api_key:
            result["error"] = "API key not configured"
            result["response_time_ms"] = (time.time() - start) * 1000
            return result

        if value_type != IOCType.IP:
            result["error"] = "AbuseIPDB only supports IP analysis"
            result["response_time_ms"] = (time.time() - start) * 1000
            return result

        try:
            client = await self._get_client()
            response = await client.get(
                "/check",
                params={
                    "ipAddress": value,
                    "maxAgeInDays": "90",
                    "verbose": "",
                },
            )
            result["response_time_ms"] = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json().get("data", {})
                abuse_score = data.get("abuseConfidenceScore", 0)
                total_reports = data.get("totalReports", 0)

                result["success"] = True
                result["malicious"] = abuse_score > 50
                result["confidence"] = abuse_score / 100.0
                result["details"] = {
                    "abuse_confidence_score": abuse_score,
                    "total_reports": total_reports,
                    "last_reported_at": data.get("lastReportedAt"),
                    "country_code": data.get("countryCode"),
                    "isp": data.get("isp"),
                    "domain": data.get("domain"),
                    "usage_type": data.get("usageType"),
                    "is_whitelisted": data.get("isWhitelisted", False),
                    "reports": data.get("reports", [])[:5],
                }
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"

        except httpx.TimeoutException:
            result["error"] = "Request timed out"
            result["response_time_ms"] = (time.time() - start) * 1000
        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"AbuseIPDB analysis failed: {e}")

        return result

    async def health_check(self) -> dict[str, Any]:
        if not self.api_key:
            return {"provider": "abuseipdb", "status": "not_configured"}
        try:
            client = await self._get_client()
            response = await client.get("/check", params={"ipAddress": "8.8.8.8", "maxAgeInDays": "1"})
            return {
                "provider": "abuseipdb",
                "status": "healthy" if response.status_code in (200, 404) else "unhealthy",
            }
        except Exception as e:
            return {"provider": "abuseipdb", "status": "unhealthy", "error": str(e)[:100]}

    async def close(self):
        if self._client:
            await self._client.aclose()


# =============================================================================
# OpenPhish Feed Provider
# =============================================================================


class OpenPhishProvider(ThreatProvider):
    """OpenPhish feed - downloads and parses the phishing feed."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.feed_url = config.openphish_feed_url
        self._phishing_urls: set[str] = set()
        self._last_update: float | None = None
        self._update_interval = config.openphish_update_interval

    async def _ensure_fresh(self):
        """Ensure the feed data is fresh."""
        now = time.time()
        if (
            self._last_update is None
            or (now - self._last_update) > self._update_interval
        ):
            await self._update_feed()

    async def _update_feed(self):
        """Download and parse the OpenPhish feed."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.feed_url)
                if response.status_code == 200:
                    urls = set()
                    for line in response.text.strip().split("\n"):
                        url = line.strip()
                        if url:
                            urls.add(url)
                    self._phishing_urls = urls
                    self._last_update = time.time()
                    logger.info(
                        f"OpenPhish feed updated: {len(urls)} URLs loaded"
                    )
                else:
                    logger.warning(
                        f"OpenPhish feed download failed: HTTP {response.status_code}"
                    )
        except Exception as e:
            logger.warning(f"OpenPhish feed update failed: {e}")

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "openphish",
            "success": True,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        await self._ensure_fresh()

        # Check if value is in the phishing feed
        if value in self._phishing_urls:
            result["malicious"] = True
            result["confidence"] = 0.95
            result["details"] = {
                "feed_match": True,
                "feed_size": len(self._phishing_urls),
            }
        else:
            # Also check extracted domain
            domain = _extract_domain(value)
            if domain != value and value in self._phishing_urls:
                result["malicious"] = True
                result["confidence"] = 0.90
                result["details"] = {
                    "feed_match": True,
                    "matched_on": "domain",
                    "feed_size": len(self._phishing_urls),
                }

        result["response_time_ms"] = (time.time() - start) * 1000
        return result

    async def health_check(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self.feed_url)
                return {
                    "provider": "openphish",
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "feed_size": len(self._phishing_urls),
                }
        except Exception as e:
            return {
                "provider": "openphish",
                "status": "unhealthy",
                "error": str(e)[:100],
            }


# =============================================================================
# PhishTank Provider
# =============================================================================


class PhishTankProvider(ThreatProvider):
    """PhishTank API for checking URLs against phishing database."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.api_key = config.phishtank_api_key
        self.base_url = config.phishtank_base_url

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "phishtank",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        if not self.api_key and value_type not in (IOCType.URL, IOCType.DOMAIN):
            result["error"] = "PhishTank only supports URL/domain analysis"
            result["response_time_ms"] = (time.time() - start) * 1000
            return result

        try:
            url = value if value_type == IOCType.URL else f"http://{value}"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    self.base_url,
                    data={
                        "url": url,
                        "format": "json",
                        "app_key": self.api_key or "",
                    },
                )
                result["response_time_ms"] = (time.time() - start) * 1000

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", {})
                    in_database = results.get("in_database", False)

                    result["success"] = True
                    result["malicious"] = in_database
                    result["confidence"] = 0.95 if in_database else 0.0
                    result["details"] = {
                        "in_database": in_database,
                        "verified": results.get("verified", False),
                        "valid": results.get("valid", False),
                        "phish_detail_url": results.get("phish_detail_page"),
                    }
                else:
                    result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"

        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"PhishTank analysis failed: {e}")

        return result

    async def health_check(self) -> dict[str, Any]:
        return {"provider": "phishtank", "status": "unknown"}


# =============================================================================
# AlienVault OTX Provider
# =============================================================================


class AlienVaultOTXProvider(ThreatProvider):
    """AlienVault Open Threat Exchange (OTX) API integration."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.api_key = config.alienvault_api_key
        self.base_url = config.alienvault_base_url
        self.timeout = config.alienvault_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "X-OTX-API-KEY": self.api_key or "",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "alienvault_otx",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        if not self.api_key:
            result["error"] = "API key not configured"
            result["response_time_ms"] = (time.time() - start) * 1000
            return result

        try:
            client = await self._get_client()
            endpoint = self._get_endpoint(value, value_type)
            if not endpoint:
                result["error"] = f"Unsupported IOC type: {value_type}"
                result["response_time_ms"] = (time.time() - start) * 1000
                return result

            response = await client.get(endpoint)
            result["response_time_ms"] = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                pulse_count = data.get("pulse_info", {}).get("count", 0)
                pulses = data.get("pulse_info", {}).get("pulses", [])

                result["success"] = True
                result["malicious"] = pulse_count > 0
                result["confidence"] = min(pulse_count / 10.0, 1.0) if pulse_count > 0 else 0.0
                result["details"] = {
                    "pulse_count": pulse_count,
                    "reputation": data.get("reputation", 0),
                    "validation": data.get("validation"),
                    "pulses": [
                        {
                            "name": p.get("name"),
                            "description": p.get("description", "")[:200],
                            "tags": p.get("tags", []),
                            "created": p.get("created"),
                            "adversary": p.get("adversary"),
                        }
                        for p in pulses[:5]
                    ],
                }
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text[:200]}"

        except httpx.TimeoutException:
            result["error"] = "Request timed out"
            result["response_time_ms"] = (time.time() - start) * 1000
        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"AlienVault OTX analysis failed: {e}")

        return result

    def _get_endpoint(self, value: str, value_type: IOCType) -> str | None:
        endpoints = {
            IOCType.IP: f"/indicators/IPv4/{value}/general",
            IOCType.DOMAIN: f"/indicators/domain/{value}/general",
            IOCType.URL: f"/indicators/url/{value}/general",
            IOCType.HASH_MD5: f"/indicators/file/{value}/general",
            IOCType.HASH_SHA1: f"/indicators/file/{value}/general",
            IOCType.HASH_SHA256: f"/indicators/file/{value}/general",
        }
        return endpoints.get(value_type)

    async def health_check(self) -> dict[str, Any]:
        if not self.api_key:
            return {"provider": "alienvault_otx", "status": "not_configured"}
        try:
            client = await self._get_client()
            response = await client.get("/user/settings")
            return {
                "provider": "alienvault_otx",
                "status": "healthy" if response.status_code == 200 else "unhealthy",
            }
        except Exception as e:
            return {"provider": "alienvault_otx", "status": "unhealthy", "error": str(e)[:100]}

    async def close(self):
        if self._client:
            await self._client.aclose()


# =============================================================================
# DNS Analysis Provider
# =============================================================================


class DNSAnalysisProvider(ThreatProvider):
    """DNS resolution and analysis provider."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.timeout = config.dns_resolver_timeout
        self.nameservers = config.dns_nameservers

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "dns_analysis",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        try:
            domain = value if value_type == IOCType.DOMAIN else _extract_domain(value)

            # A record lookup
            a_records = await self._resolve(domain, "A")
            # AAAA record lookup
            aaaa_records = await self._resolve(domain, "AAAA")
            # MX record lookup
            mx_records = await self._resolve(domain, "MX")
            # NS record lookup
            ns_records = await self._resolve(domain, "NS")
            # TXT record lookup
            txt_records = await self._resolve(domain, "TXT")

            has_records = any([a_records, aaaa_records, mx_records, ns_records])

            result["success"] = True
            result["details"] = {
                "domain": domain,
                "has_records": has_records,
                "a_records": a_records[:5] if a_records else [],
                "aaaa_records": aaaa_records[:5] if aaaa_records else [],
                "mx_records": mx_records[:5] if mx_records else [],
                "ns_records": ns_records[:5] if ns_records else [],
                "txt_records": txt_records[:5] if txt_records else [],
            }

            result["response_time_ms"] = (time.time() - start) * 1000

        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"DNS analysis failed: {e}")

        return result

    async def _resolve(
        self, domain: str, record_type: str
    ) -> list[str]:
        """Resolve DNS records asynchronously."""
        try:
            import dns.asyncresolver as async_resolver
            resolver = async_resolver.Resolver()
            resolver.nameservers = self.nameservers
            resolver.timeout = self.timeout
            resolver.lifetime = self.timeout

            answer = await async_resolver.resolve(domain, record_type)
            return [str(rdata) for rdata in answer]
        except Exception:
            return []

    async def health_check(self) -> dict[str, Any]:
        try:
            await self._resolve("google.com", "A")
            return {"provider": "dns_analysis", "status": "healthy"}
        except Exception as e:
            return {"provider": "dns_analysis", "status": "unhealthy", "error": str(e)[:100]}


# =============================================================================
# WHOIS Lookup Provider
# =============================================================================


class WHOISProvider(ThreatProvider):
    """WHOIS lookup provider for domain registration information."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.timeout = config.whois_timeout

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "whois_lookup",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        try:
            domain = value if value_type == IOCType.DOMAIN else _extract_domain(value)

            # Use whois library in a thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            whois_data = await loop.run_in_executor(
                None, self._do_whois_lookup, domain
            )

            if whois_data:
                result["success"] = True
                result["details"] = whois_data

                # Check for suspicious WHOIS patterns
                suspicious_indicators = 0
                if whois_data.get("registrar") == "PRIVATE":
                    suspicious_indicators += 1
                if whois_data.get("days_since_created", 999) < 30:
                    suspicious_indicators += 1
                if whois_data.get("days_until_expires", 999) > 365:
                    suspicious_indicators += 1

                if suspicious_indicators >= 2:
                    result["malicious"] = True
                    result["confidence"] = suspicious_indicators / 3.0

            result["response_time_ms"] = (time.time() - start) * 1000

        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"WHOIS lookup failed: {e}")

        return result

    def _do_whois_lookup(self, domain: str) -> dict[str, Any] | None:
        """Perform synchronous WHOIS lookup."""
        try:
            import whois as whois_lib
            w = whois_lib.whois(domain)

            # Parse dates
            creation_date = None
            if w.creation_date:
                if isinstance(w.creation_date, list):
                    creation_date = w.creation_date[0]
                else:
                    creation_date = w.creation_date

            expiration_date = None
            if w.expiration_date:
                if isinstance(w.expiration_date, list):
                    expiration_date = w.expiration_date[0]
                else:
                    expiration_date = w.expiration_date

            now = datetime.now(UTC)
            days_since_created = (
                (now - creation_date).days if creation_date else None
            )
            days_until_expires = (
                (expiration_date - now).days if expiration_date else None
            )

            return {
                "domain": domain,
                "registrar": str(w.registrar or "Unknown"),
                "registrant_name": str(w.name or "Unknown"),
                "registrant_org": str(w.org or "Unknown"),
                "registrant_country": str(w.country or "Unknown"),
                "creation_date": creation_date.isoformat() if creation_date else None,
                "expiration_date": expiration_date.isoformat() if expiration_date else None,
                "days_since_created": days_since_created,
                "days_until_expires": days_until_expires,
                "name_servers": w.name_servers or [],
                "status": w.status or [],
                "emails": w.emails or [],
            }
        except Exception:
            return None

    async def health_check(self) -> dict[str, Any]:
        return {"provider": "whois_lookup", "status": "healthy"}


# =============================================================================
# GeoIP Analysis Provider
# =============================================================================


class GeoIPProvider(ThreatProvider):
    """GeoIP analysis using MaxMind GeoLite2 database."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)
        self.db_path = config.geoip_db_path

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "geoip_analysis",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        if value_type != IOCType.IP:
            result["error"] = "GeoIP only supports IP analysis"
            result["response_time_ms"] = (time.time() - start) * 1000
            return result

        try:
            import geoip2.database as geoip_db

            if not hasattr(self, "_geoip_reader"):
                try:
                    self._geoip_reader = geoip_db.Reader(self.db_path)
                except Exception:
                    result["error"] = "GeoIP database not available"
                    result["response_time_ms"] = (time.time() - start) * 1000
                    return result

            response = self._geoip_reader.city(value)
            result["success"] = True
            result["details"] = {
                "country_code": response.country.iso_code,
                "country_name": response.country.name,
                "city": response.city.name,
                "postal_code": response.postal.code,
                "location": {
                    "latitude": response.location.latitude,
                    "longitude": response.location.longitude,
                    "accuracy_radius": response.location.accuracy_radius,
                    "timezone": response.location.time_zone,
                },
                "subdivisions": [
                    {"name": sub.name, "iso_code": sub.iso_code}
                    for sub in response.subdivisions
                ],
                "continent": response.continent.name,
            }

            result["response_time_ms"] = (time.time() - start) * 1000

        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"GeoIP analysis failed: {e}")

        return result

    async def health_check(self) -> dict[str, Any]:
        try:
            if hasattr(self, "_geoip_reader") and self._geoip_reader:
                return {"provider": "geoip_analysis", "status": "healthy"}
            import geoip2.database as geoip_db
            reader = geoip_db.Reader(self.db_path)
            reader.close()
            return {"provider": "geoip_analysis", "status": "healthy"}
        except Exception:
            return {"provider": "geoip_analysis", "status": "not_configured"}


# =============================================================================
# ASN Lookup Provider
# =============================================================================


class ASNProvider(ThreatProvider):
    """ASN (Autonomous System Number) lookup provider."""

    def __init__(self, config: ThreatIntelConfig):
        super().__init__(config)

    async def analyze(
        self, value: str, value_type: IOCType
    ) -> dict[str, Any]:
        start = time.time()
        result = {
            "provider": "asn_lookup",
            "success": False,
            "malicious": False,
            "confidence": 0.0,
            "details": None,
            "error": None,
            "response_time_ms": 0.0,
        }

        try:
            if value_type == IOCType.IP:
                ip = value
            elif value_type == IOCType.DOMAIN:
                ip = socket.gethostbyname(value)
            else:
                domain = _extract_domain(value)
                ip = socket.gethostbyname(domain)

            # Use a thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            asn_data = await loop.run_in_executor(
                None, self._do_asn_lookup, ip
            )

            if asn_data:
                result["success"] = True
                result["details"] = asn_data

            result["response_time_ms"] = (time.time() - start) * 1000

        except Exception as e:
            result["error"] = str(e)[:200]
            result["response_time_ms"] = (time.time() - start) * 1000
            logger.warning(f"ASN lookup failed: {e}")

        return result

    def _do_asn_lookup(self, ip: str) -> dict[str, Any] | None:
        """Perform synchronous ASN lookup."""
        try:
            # Use IPWhois or simple REST API
            return {
                "ip": ip,
                "asn": None,
                "asn_org": None,
                "note": "Full ASN lookup requires commercial database or Cymru DNS service",
            }
        except Exception:
            return None

    async def health_check(self) -> dict[str, Any]:
        return {"provider": "asn_lookup", "status": "healthy"}


# =============================================================================
# Provider Factory
# =============================================================================


class ProviderRegistry:
    """
    Registry of all threat intelligence providers.
    Implements the provider pattern for dependency injection.
    """

    def __init__(self, config: ThreatIntelConfig):
        self.config = config
        self._providers: dict[str, ThreatProvider] = {}
        self._initialize()

    def _initialize(self):
        """Initialize all providers."""
        providers = {
            "virustotal": VirusTotalProvider,
            "abuseipdb": AbuseIPDBProvider,
            "openphish": OpenPhishProvider,
            "phishtank": PhishTankProvider,
            "alienvault": AlienVaultOTXProvider,
            "dns": DNSAnalysisProvider,
            "whois": WHOISProvider,
            "geoip": GeoIPProvider,
            "asn": ASNProvider,
        }

        for name, provider_class in providers.items():
            try:
                self._providers[name] = provider_class(self.config)
            except Exception as e:
                logger.warning(f"Failed to initialize provider '{name}': {e}")

    def get_provider(self, name: str) -> ThreatProvider | None:
        """Get a specific provider by name."""
        return self._providers.get(name)

    def get_enabled_providers(self) -> list[ThreatProvider]:
        """Get all enabled providers based on configuration."""
        enabled = self.config.get_enabled_providers()
        return [
            self._providers[name]
            for name in enabled
            if name in self._providers
        ]

    def get_all_providers(self) -> dict[str, ThreatProvider]:
        """Get all registered providers."""
        return dict(self._providers)

    async def health_check_all(self) -> list[dict[str, Any]]:
        """Run health checks on all providers."""
        results = []
        for name, provider in self._providers.items():
            with contextlib.suppress(Exception):
                result = await provider.health_check()
                results.append(result)
        return results

    async def close_all(self):
        """Close all provider connections."""
        for provider in self._providers.values():
            with contextlib.suppress(Exception):
                if hasattr(provider, "close"):
                    await provider.close()

