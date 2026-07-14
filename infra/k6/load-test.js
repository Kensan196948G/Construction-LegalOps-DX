/**
 * k6 load test suite — Construction LegalOps DX
 *
 * Scenarios:
 *   smoke  — 5 VU / 30s: basic sanity check (run before every release)
 *   load   — ramp to 20 VU over 1min, hold 3min, ramp down: SLO gate
 *   soak   — 10 VU / 10min: detect memory leaks / slow degradation
 *
 * SLO:  p(95) < 500ms, error rate < 1%
 *
 * Usage:
 *   k6 run -e SCENARIO=smoke  infra/k6/load-test.js
 *   k6 run -e SCENARIO=load   infra/k6/load-test.js
 *   k6 run -e SCENARIO=soak   infra/k6/load-test.js
 *
 * Optional env vars:
 *   BASE_URL    — target (default: http://localhost:8000)
 *   JWT_TOKEN   — Bearer token for authenticated endpoint checks
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const errorRate = new Rate("custom_error_rate");
const dbLatency = new Trend("db_query_latency_ms"); // readyz (includes DB SELECT 1)

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const JWT_TOKEN = __ENV.JWT_TOKEN || "";
const SCENARIO = __ENV.SCENARIO || "smoke";

const SCENARIOS = {
  smoke: {
    executor: "constant-vus",
    vus: 5,
    duration: "30s",
  },
  load: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "1m", target: 20 }, // ramp up
      { duration: "3m", target: 20 }, // hold at 20 VU ≈ 50+ req/s
      { duration: "30s", target: 0 }, // ramp down
    ],
  },
  soak: {
    executor: "constant-vus",
    vus: 10,
    duration: "10m",
  },
};

export const options = {
  scenarios: {
    [SCENARIO]: SCENARIOS[SCENARIO],
  },
  thresholds: {
    // Global SLO
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
    // Custom metrics
    custom_error_rate: ["rate<0.01"],
    db_query_latency_ms: ["p(95)<800"], // readyz includes async DB ping
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function baseHeaders() {
  const h = { "Content-Type": "application/json" };
  if (JWT_TOKEN) {
    h["Authorization"] = `Bearer ${JWT_TOKEN}`;
  }
  return h;
}

function recordError(res, label) {
  const ok = res.status >= 200 && res.status < 400;
  errorRate.add(!ok, { endpoint: label });
  return ok;
}

// ---------------------------------------------------------------------------
// Test groups
// ---------------------------------------------------------------------------

/** Liveness / ping — pure process-level probes, no DB. */
function testLiveness() {
  const res = http.get(`${BASE_URL}/healthz`);
  const ok = check(res, {
    "healthz: status 200": (r) => r.status === 200,
    "healthz: body ok": (r) => {
      try {
        return JSON.parse(r.body).status === "ok";
      } catch {
        return false;
      }
    },
  });
  recordError(res, "/healthz");

  // NOTE: /ping is mounted under the v1 router (app/api/v1/health.py) — the
  // root path does not exist and 404'd every iteration on the first real run.
  const ping = http.get(`${BASE_URL}/api/v1/ping`);
  check(ping, {
    "ping: status 200": (r) => r.status === 200,
    "ping: body pong": (r) => {
      try {
        return JSON.parse(r.body).status === "pong";
      } catch {
        return false;
      }
    },
  });
  recordError(ping, "/api/v1/ping");
}

/** Readiness deep check — hits DB (SELECT 1) and optional Redis/Claude. */
function testReadiness() {
  const start = Date.now();
  const res = http.get(`${BASE_URL}/readyz`);
  dbLatency.add(Date.now() - start);

  check(res, {
    "readyz: not 503": (r) => r.status !== 503,
    "readyz: db ok": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.checks && body.checks.db && body.checks.db.status === "ok";
      } catch {
        return false;
      }
    },
  });
  recordError(res, "/readyz");
}

/** API endpoints — contract + knowledge list (public-ish; uses JWT if provided). */
function testApiEndpoints() {
  const headers = baseHeaders();

  const routes = [
    "/api/v1/contracts",
    "/api/v1/reviews",
    "/api/v1/risks",
    "/api/v1/knowledge",
  ];

  for (const route of routes) {
    const res = http.get(`${BASE_URL}${route}`, { headers });
    // 401/403 means auth required but test skips gracefully
    const ok = check(res, {
      [`${route}: not 5xx`]: (r) => r.status < 500,
    });
    recordError(res, route);
    if (!ok) break; // abort series on server error
  }
}

// ---------------------------------------------------------------------------
// Main VU function
// ---------------------------------------------------------------------------
export default function () {
  testLiveness();
  sleep(0.2);

  // Only probe readyz every 5th iteration to reduce DB load during high-VU runs
  if (__ITER % 5 === 0) {
    testReadiness();
    sleep(0.1);
  }

  if (JWT_TOKEN) {
    testApiEndpoints();
    sleep(0.3);
  }

  sleep(0.5);
}

// ---------------------------------------------------------------------------
// Summary callback — print final verdict
// ---------------------------------------------------------------------------
export function handleSummary(data) {
  const p95 = data.metrics.http_req_duration
    ? data.metrics.http_req_duration.values["p(95)"]
    : null;
  const errRate = data.metrics.http_req_failed
    ? data.metrics.http_req_failed.values.rate
    : null;

  const verdict =
    p95 !== null && p95 < 500 && errRate !== null && errRate < 0.01
      ? "✅ PASS — SLO 達成 (p95 < 500ms, error < 1%)"
      : "❌ FAIL — SLO 未達";

  console.log("\n" + "=".repeat(60));
  console.log(`[k6] Scenario: ${SCENARIO.toUpperCase()}`);
  console.log(`[k6] p(95): ${p95 !== null ? p95.toFixed(1) + "ms" : "N/A"}`);
  console.log(
    `[k6] Error rate: ${errRate !== null ? (errRate * 100).toFixed(2) + "%" : "N/A"}`
  );
  console.log(`[k6] ${verdict}`);
  console.log("=".repeat(60) + "\n");

  return {
    stdout: JSON.stringify(data, null, 2),
  };
}
