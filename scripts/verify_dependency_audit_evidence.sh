#!/usr/bin/env bash
# verify_dependency_audit_evidence.sh — read-only dependency audit evidence.
#
# This script validates the release dependency-audit boundary without changing
# dependencies or applying automated fixes. It checks live npm high/critical
# status, documents known moderate npm findings, and verifies that Python
# dependency audit is configured with strict, project-scoped pip-audit rules.

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

contains_file() {
  local file="$1"
  local pattern="$2"
  grep -Fq -- "$pattern" "$file"
}

json_value() {
  local file="$1"
  local expr="$2"
  node -e "const fs=require('fs'); const j=JSON.parse(fs.readFileSync(process.argv[1], 'utf8')); const fn=${expr}; console.log(fn(j));" "${file}"
}

echo "================================================"
echo "🧬 Dependency Audit Evidence Preflight"
echo "================================================"

NPM_AUDIT_JSON="${NPM_AUDIT_JSON:-/tmp/legalops-npm-audit-high.json}"
PIP_AUDIT_JSON="${PIP_AUDIT_JSON:-/tmp/legalops-pip-audit.json}"

for file in "frontend/package-lock.json" "frontend/package.json" "backend/pyproject.toml" ".github/workflows/security.yml" "docs/RELEASE_EVIDENCE_MATRIX.md" "docs/FINAL_RELEASE_STOP_REPORT.md"; do
  [ -s "${file}" ] && pass "Dependency evidence source exists: ${file}" || fail "Dependency evidence source missing or empty: ${file}"
done

if (cd frontend && npm audit --audit-level=high --json > "${NPM_AUDIT_JSON}"); then
  pass "npm audit high+ command exits successfully"
else
  fail "npm audit high+ command failed"
fi

NPM_HIGH="$(json_value "${NPM_AUDIT_JSON}" "j => (j.metadata && j.metadata.vulnerabilities && j.metadata.vulnerabilities.high) || 0")"
NPM_CRITICAL="$(json_value "${NPM_AUDIT_JSON}" "j => (j.metadata && j.metadata.vulnerabilities && j.metadata.vulnerabilities.critical) || 0")"
NPM_MODERATE="$(json_value "${NPM_AUDIT_JSON}" "j => (j.metadata && j.metadata.vulnerabilities && j.metadata.vulnerabilities.moderate) || 0")"

[ "${NPM_HIGH}" = "0" ] && pass "npm audit high vulnerabilities are 0" || fail "npm audit high vulnerabilities are ${NPM_HIGH}"
[ "${NPM_CRITICAL}" = "0" ] && pass "npm audit critical vulnerabilities are 0" || fail "npm audit critical vulnerabilities are ${NPM_CRITICAL}"
[ "${NPM_MODERATE}" = "4" ] && pass "npm audit moderate vulnerabilities are documented as 4" || fail "npm audit moderate vulnerabilities are ${NPM_MODERATE}; expected documented 4"

contains_file "scripts/pre_deploy_check.sh" "npm audit --audit-level=high" && pass "Pre-deploy gate runs npm audit high+" || fail "Pre-deploy gate missing npm audit high+"
contains_file ".github/workflows/security.yml" "pip-audit -r resolved-requirements.txt --strict" && pass "Security workflow runs strict project-scoped pip-audit" || fail "Security workflow missing strict pip-audit"
contains_file ".github/workflows/security.yml" "pip freeze --exclude-editable" && pass "Security workflow avoids auditing unpublished editable package" || fail "Security workflow missing freeze --exclude-editable"
contains_file ".github/workflows/security.yml" "ambient pip" && pass "Security workflow documents ambient pip false-positive guard" || fail "Security workflow missing ambient pip rationale"
contains_file ".github/workflows/security.yml" "--ignore-vuln PYSEC-2026-1325" && pass "Security workflow records ecdsa PYSEC ignore" || fail "Security workflow missing PYSEC ignore"
contains_file ".github/workflows/security.yml" "到達不能" && pass "Security workflow documents ecdsa reachability rationale" || fail "Security workflow missing ecdsa reachability rationale"
contains_file "backend/pyproject.toml" "PyJWT[crypto]" && pass "Backend uses PyJWT crypto dependency" || fail "Backend missing PyJWT crypto dependency"

if grep -Fq "python-jose" backend/pyproject.toml; then
  fail "backend/pyproject.toml still depends on python-jose"
else
  pass "backend/pyproject.toml does not depend on python-jose"
fi

if [ -s "${PIP_AUDIT_JSON}" ]; then
  PIP_VULNS="$(
    python3 - "${PIP_AUDIT_JSON}" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(sum(len(dep.get("vulns", [])) for dep in data.get("dependencies", [])))
PY
  )"
  [ "${PIP_VULNS}" = "0" ] && pass "Latest local pip-audit artifact has 0 vulnerabilities" || fail "Latest local pip-audit artifact has ${PIP_VULNS} vulnerabilities"
else
  pass "Local pip-audit artifact is optional; CI workflow is the authoritative recurring Python dependency audit"
fi

contains_file "docs/RELEASE_EVIDENCE_MATRIX.md" "npm audit high/critical 0" && pass "Evidence matrix records npm audit high/critical result" || fail "Evidence matrix missing npm audit high/critical result"
contains_file "docs/RELEASE_EVIDENCE_MATRIX.md" "moderate 4" && pass "Evidence matrix records npm moderate known risk" || fail "Evidence matrix missing npm moderate known risk"
contains_file "docs/RELEASE_EVIDENCE_MATRIX.md" "pip-audit" && pass "Evidence matrix records pip-audit evidence" || fail "Evidence matrix missing pip-audit evidence"
contains_file "docs/FINAL_RELEASE_STOP_REPORT.md" "npm audit high/critical 0" && pass "Final report records npm audit high/critical result" || fail "Final report missing npm audit high/critical result"

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Dependency audit evidence preflight failed"
  exit 1
fi

echo "✅ Dependency audit evidence preflight passed"
exit 0
