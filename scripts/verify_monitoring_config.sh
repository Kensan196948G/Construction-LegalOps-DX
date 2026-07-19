#!/usr/bin/env bash
# verify_monitoring_config.sh — read-only monitoring/IaC consistency checks.
#
# This script validates Prometheus/Grafana/Alertmanager configuration and
# documentation. It does not start services, open ports, or contact production.

set -euo pipefail

PASS=0
FAIL=0

pass() {
  echo "✅ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ $1"
  FAIL=$((FAIL + 1))
}

contains() {
  local file="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$file"
}

echo "================================================"
echo "📊 Monitoring Config Preflight"
echo "================================================"

PROM="infra/monitoring/prometheus.yml"
ALERTS="infra/monitoring/alert.rules.yml"
ALERTMANAGER="infra/monitoring/alertmanager.yml"
GRAFANA="infra/monitoring/grafana-dashboard.json"
DOC="docs/MONITORING.md"
COMPOSE="infra/docker/docker-compose.prod.yml"

for file in "${PROM}" "${ALERTS}" "${ALERTMANAGER}" "${GRAFANA}" "${DOC}" "${COMPOSE}"; do
  [ -s "${file}" ] && pass "Required monitoring file exists: ${file}" || fail "Required monitoring file missing: ${file}"
done

python3 - <<'PY' >/dev/null && pass "Monitoring YAML/JSON files parse" || fail "Monitoring YAML/JSON parse failed"
import json
from pathlib import Path

import yaml

for name in [
    "infra/monitoring/prometheus.yml",
    "infra/monitoring/alert.rules.yml",
    "infra/monitoring/alertmanager.yml",
]:
    yaml.safe_load(Path(name).read_text())
json.loads(Path("infra/monitoring/grafana-dashboard.json").read_text())
PY

contains "${PROM}" 'job_name: "legalops-backend"' && pass "Prometheus has legalops-backend job" || fail "Prometheus missing backend job"
contains "${PROM}" "dns_sd_configs:" && pass "Prometheus uses DNS service discovery for backend" || fail "Prometheus missing DNS service discovery"
contains "${PROM}" 'names: ["backend"]' && pass "Prometheus discovers backend service name" || fail "Prometheus missing backend DNS name"
contains "${PROM}" "port: 8000" && pass "Prometheus discovers backend port 8000" || fail "Prometheus missing backend port"
contains "${PROM}" 'job_name: "legalops-nginx"' && pass "Prometheus has nginx job" || fail "Prometheus missing nginx job"
contains "${PROM}" 'targets: ["nginx-exporter:9113"]' && pass "Prometheus scrapes nginx exporter" || fail "Prometheus missing nginx exporter target"

contains "${COMPOSE}" "replicas: 2" && pass "Production overlay records replicated services" || fail "Production overlay missing replica configuration"
contains "${COMPOSE}" "container_name: !reset null" && pass "Production overlay removes fixed container names for replicas" || fail "Production overlay missing container_name reset"

contains "${DOC}" "Docker DNS service discovery" && pass "Monitoring docs explain Docker DNS discovery" || fail "Monitoring docs missing Docker DNS discovery"
contains "${DOC}" 'dns_sd_configs' && pass "Monitoring docs include dns_sd_configs" || fail "Monitoring docs missing dns_sd_configs"
contains "${DOC}" "各レプリカの \`/metrics\`" && pass "Monitoring docs explain per-replica metrics scrape" || fail "Monitoring docs missing per-replica scrape explanation"

if grep -Fq "multiprocess 集約は未実装" "${DOC}"; then
  fail "Monitoring docs still describe metrics aggregation as unimplemented"
else
  pass "Monitoring docs no longer contain stale multiprocess unimplemented wording"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Monitoring config preflight failed"
  exit 1
fi

echo "✅ Monitoring config preflight passed"
