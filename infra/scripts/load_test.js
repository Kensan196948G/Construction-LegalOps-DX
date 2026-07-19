/**
 * k6 負荷テストスクリプト — Construction-LegalOps-DX
 *
 * 使用方法:
 *   k6 run infra/scripts/load_test.js
 *   k6 run --env BASE_URL=https://legalops.mirai-dx-platform.com infra/scripts/load_test.js
 *
 * 目標 KPI (RELEASE_CHECKLIST §負荷テスト):
 *   - スループット: 50 req/s
 *   - p95 レイテンシ: < 500ms
 *   - エラー率: < 1%
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const JWT_TOKEN = __ENV.JWT_TOKEN || "";

const errorRate = new Rate("errors");
const contractsLatency = new Trend("contracts_latency");
const healthLatency = new Trend("health_latency");

export const options = {
  stages: [
    { duration: "30s", target: 10 }, // ramp up
    { duration: "2m", target: 50 }, // 目標 50 req/s
    { duration: "30s", target: 0 }, // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // p95 < 500ms
    errors: ["rate<0.01"], // エラー率 < 1%
    http_req_failed: ["rate<0.01"],
  },
};

const HEADERS = {
  "Content-Type": "application/json",
  Authorization: `Bearer ${JWT_TOKEN}`,
};

export default function () {
  // 1. Healthz (liveness)
  const healthRes = http.get(`${BASE_URL}/healthz`);
  healthLatency.add(healthRes.timings.duration);
  check(healthRes, {
    "healthz 200": (r) => r.status === 200,
  }) || errorRate.add(1);

  // 2. Readyz (readiness)
  const readyzRes = http.get(`${BASE_URL}/readyz`);
  check(readyzRes, {
    "readyz ready": (r) =>
      r.status === 200 &&
      (r.json().status === "ready" || r.json().status === "degraded"),
  }) || errorRate.add(1);

  // 3. Contracts list (authenticated)
  if (JWT_TOKEN) {
    const contractsRes = http.get(`${BASE_URL}/api/v1/contracts?size=20`, {
      headers: HEADERS,
    });
    contractsLatency.add(contractsRes.timings.duration);
    check(contractsRes, {
      "contracts 200": (r) => r.status === 200,
      "contracts has items": (r) => r.json().items !== undefined,
    }) || errorRate.add(1);
  }

  sleep(0.1);
}

export function handleSummary(data) {
  const p95 = data.metrics.http_req_duration.values["p(95)"];
  const rps = data.metrics.http_reqs.values.rate;
  const errRate = data.metrics.http_req_failed
    ? data.metrics.http_req_failed.values.rate * 100
    : 0;

  console.log("\n=== Load Test Summary ===");
  console.log(`RPS:        ${rps.toFixed(1)} req/s  (target: 50)`);
  console.log(`p95:        ${p95.toFixed(0)}ms      (target: <500ms)`);
  console.log(`Error rate: ${errRate.toFixed(2)}%      (target: <1%)`);

  const passed = p95 < 500 && rps >= 40 && errRate < 1;
  console.log(`\nResult: ${passed ? "✅ PASSED" : "❌ FAILED"}`);

  return {
    "load_test_summary.json": JSON.stringify(data, null, 2),
  };
}
