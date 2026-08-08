"""
Validate all YAML files in the repository parse correctly.
Supports multi-document YAML (k8s manifests).
"""
import glob
import sys

import yaml

# Files that are k8s manifests or alert rules (multi-document YAML)
YAML_FILES = [
    ".github/workflows/ci.yml",
    ".github/workflows/cd.yml",
    ".github/workflows/security-scan.yml",
    ".github/workflows/codeql.yml",
    ".github/dependabot.yml",
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "docker-compose.prod.yml",
    "docker-compose.monitoring.yml",
    "deploy/environments/staging.yaml",
    "deploy/environments/production.yaml",
    "deploy/k8s/kustomization.yaml",
    "monitoring/prometheus/prometheus.yml",
    "monitoring/prometheus/alerts.yml",
    "monitoring/promtail/config.yml",
    "monitoring/grafana/datasources/datasources.yml",
    "monitoring/grafana/dashboards/dashboard.yml",
] + glob.glob("deploy/k8s/*.yaml") + glob.glob("deploy/k8s/*.yml")

failures = []
for path in sorted(set(YAML_FILES)):
    try:
        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        # Ensure at least one non-empty document
        if not any(doc is not None for doc in docs):
            failures.append(f"{path}: empty document")
        else:
            print(f"OK   {path}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{path}: {exc}")
        print(f"FAIL {path}: {exc}")

print("-" * 60)
if failures:
    print(f"FAILED: {len(failures)} file(s) invalid")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)
print("ALL YAML VALID")
