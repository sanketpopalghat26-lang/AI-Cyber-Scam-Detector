"""
Threat Intelligence Configuration
==================================
Centralized configuration for the Threat Intelligence Center module.
All secrets and settings are loaded from environment variables in production.
"""

import os
from dataclasses import dataclass, field


@dataclass
class ThreatIntelConfig:
    """
    Configuration for the Threat Intelligence Center.

    All values can be overridden via environment variables with the
    THREAT_INTEL_ prefix for production deployments.
    """

    # Feature flag
    enabled: bool = os.getenv("ENABLE_THREAT_INTEL", "true").lower() == "true"

    # IOC Database
    ioc_cache_ttl: int = int(os.getenv("THREAT_INTEL_IOC_CACHE_TTL", "300"))  # 5 minutes
    ioc_max_results: int = int(os.getenv("THREAT_INTEL_IOC_MAX_RESULTS", "1000"))
    ioc_auto_update_interval: int = int(
        os.getenv("THREAT_INTEL_IOC_AUTO_UPDATE_INTERVAL", "3600")
    )  # 1 hour

    # VirusTotal
    virustotal_api_key: str | None = os.getenv("VIRUSTOTAL_API_KEY")
    virustotal_base_url: str = os.getenv(
        "VIRUSTOTAL_BASE_URL", "https://www.virustotal.com/api/v3"
    )
    virustotal_timeout: int = int(os.getenv("VIRUSTOTAL_TIMEOUT", "10"))

    # AbuseIPDB
    abuseipdb_api_key: str | None = os.getenv("ABUSEIPDB_API_KEY")
    abuseipdb_base_url: str = os.getenv(
        "ABUSEIPDB_BASE_URL", "https://api.abuseipdb.com/api/v2"
    )
    abuseipdb_timeout: int = int(os.getenv("ABUSEIPDB_TIMEOUT", "10"))

    # OpenPhish
    openphish_feed_url: str = os.getenv(
        "OPENPHISH_FEED_URL", "https://openphish.com/feed.txt"
    )
    openphish_update_interval: int = int(
        os.getenv("OPENPHISH_UPDATE_INTERVAL", "1800")
    )  # 30 minutes

    # PhishTank
    phishtank_api_key: str | None = os.getenv("PHISHTANK_API_KEY")
    phishtank_base_url: str = os.getenv(
        "PHISHTANK_BASE_URL", "https://checkurl.phishtank.com/checkurl"
    )
    phishtank_update_interval: int = int(
        os.getenv("PHISHTANK_UPDATE_INTERVAL", "3600")
    )

    # AlienVault OTX
    alienvault_api_key: str | None = os.getenv("ALIENVAULT_OTX_API_KEY")
    alienvault_base_url: str = os.getenv(
        "ALIENVAULT_OTX_BASE_URL", "https://otx.alienvault.com/api/v1"
    )
    alienvault_timeout: int = int(os.getenv("ALIENVAULT_TIMEOUT", "10"))

    # GeoIP
    geoip_db_path: str = os.getenv(
        "GEOIP_DB_PATH", "/app/data/geolite2-city.mmdb"
    )
    maxmind_license_key: str | None = os.getenv("MAXMIND_LICENSE_KEY")

    # DNS
    dns_resolver_timeout: float = float(
        os.getenv("DNS_RESOLVER_TIMEOUT", "5.0")
    )
    dns_nameservers: list[str] = field(
        default_factory=lambda: os.getenv("DNS_NAMESERVERS", "8.8.8.8,1.1.1.1").split(
            ","
        )
    )

    # WHOIS
    whois_timeout: int = int(os.getenv("WHOIS_TIMEOUT", "10"))

    # ASN
    asn_cache_ttl: int = int(os.getenv("ASN_CACHE_TTL", "86400"))  # 24 hours

    # Rate limiting specific to threat intel endpoints
    threat_intel_rate_limit: int = int(
        os.getenv("THREAT_INTEL_RATE_LIMIT", "30")
    )
    threat_intel_rate_window: int = int(
        os.getenv("THREAT_INTEL_RATE_WINDOW", "60")
    )

    # Threat scoring
    threat_score_weights: dict[str, float] = field(
        default_factory=lambda: {
            "virustotal": 0.25,
            "abuseipdb": 0.20,
            "phishtank": 0.20,
            "openphish": 0.15,
            "alienvault": 0.10,
            "dns": 0.05,
            "whois": 0.05,
        }
    )

    # Risk thresholds
    risk_threshold_high: float = float(os.getenv("RISK_THRESHOLD_HIGH", "0.7"))
    risk_threshold_medium: float = float(
        os.getenv("RISK_THRESHOLD_MEDIUM", "0.4")
    )

    @classmethod
    def from_env(cls) -> "ThreatIntelConfig":
        """Create configuration from environment variables."""
        return cls()

    def is_fully_configured(self) -> bool:
        """Check if at least one threat intel provider is configured."""
        return bool(
            self.virustotal_api_key
            or self.abuseipdb_api_key
            or self.phishtank_api_key
            or self.alienvault_api_key
        )

    def get_enabled_providers(self) -> list[str]:
        """Return list of enabled provider names."""
        providers = []
        if self.virustotal_api_key:
            providers.append("virustotal")
        if self.abuseipdb_api_key:
            providers.append("abuseipdb")
        if self.phishtank_api_key:
            providers.append("phishtank")
        if self.alienvault_api_key:
            providers.append("alienvault")
        providers.extend(["openphish", "dns", "whois", "geoip"])
        return providers

