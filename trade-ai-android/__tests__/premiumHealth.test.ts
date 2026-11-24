import {
  healthStatus,
  observeHealth,
  observedDuration,
  type HealthInput,
} from "../src/domain/scannerHealth";
const now = 1800000000000;
const base: HealthInput = {
  now,
  observedAt: now,
  gatewayVerified: true,
  mode: "live",
  account: "MANUAL",
  accounts: ["MANUAL"],
  scopes: ["read"],
  runtime: {
    provider_status: "reachable",
    last_attempt_ms: now,
    last_success_ms: now,
    activation: {
      state: "active",
      reasons: [],
      runtime_available: true,
      account_enabled: true,
      starts_process: false,
    },
  },
};
test.each([
  ["ONLINE", {}],
  ["OFFLINE", { deviceOnline: false }],
  ["BACKEND_UNAVAILABLE", { errorCode: "BACKEND_UNAVAILABLE" }],
  ["GATEWAY_UNAVAILABLE", { errorCode: "GATEWAY_UNAVAILABLE" }],
  [
    "PROVIDER_UNAVAILABLE",
    { runtime: { ...base.runtime, provider_status: "circuit_open" } },
  ],
  [
    "WORKER_INACTIVE",
    {
      runtime: {
        provider_status: "reachable",
        activation: {
          state: "blocked",
          reasons: ["runtime_not_running"],
          runtime_available: false,
          account_enabled: true,
          starts_process: false,
        },
      },
    },
  ],
  ["UNAUTHORIZED", { errorStatus: 403 }],
  ["DEGRADED", { observedAt: now - 120001 }],
  ["RECOVERING", { recovering: true }],
  ["UNKNOWN", { errorCode: "NETWORK" }],
] as const)("evidence maps to %s", (status, extra) =>
  expect(healthStatus({ ...base, ...extra }).status).toBe(status),
);
test("a generic fetch error proves neither phone offline nor gateway down", () => {
  const h = healthStatus({ ...base, errorCode: "NETWORK" });
  expect(h.status).toBe("UNKNOWN");
  expect(h.detail).toContain("varsayılmaz");
});
test("explicit recovery outranks the previous failed backend observation", () =>
  expect(
    healthStatus({
      ...base,
      errorCode: "BACKEND_UNAVAILABLE",
      recovering: true,
    }).status,
  ).toBe("RECOVERING"));
test("stale or future observations never claim worker inactive or online", () => {
  expect(healthStatus({ ...base, observedAt: now + 1 }).status).toBe(
    "DEGRADED",
  );
  expect(healthStatus({ ...base, stale: true }).status).toBe("DEGRADED");
  expect(
    healthStatus({ ...base, runtime: { activation: { state: "active" } } })
      .status,
  ).toBe("DEGRADED");
});
test("failure duration starts only at observation, recovery and account scope reset it", () => {
  let m = {
    scope: "MANUAL",
    failedSince: null as number | null,
    lastRecoveredAt: null as number | null,
  };
  m = observeHealth(m, "MANUAL", now, true, false);
  expect(m.failedSince).toBe(now);
  expect(observeHealth(m, "MANUAL", now + 5000, true, false).failedSince).toBe(
    now,
  );
  expect(observedDuration(m.failedSince, now + 60000)).toBe("1 dk");
  expect(observedDuration(m.failedSince, now - 1)).toBe("Bilinmiyor");
  m = observeHealth(m, "MANUAL", now + 60000, false, true);
  expect(m.failedSince).toBeNull();
  expect(m.lastRecoveredAt).toBe(now + 60000);
  expect(
    observeHealth(m, "AUTO", now + 60001, false, false).lastRecoveredAt,
  ).toBeNull();
});
test("a fresh backend read cannot refresh an old provider success", () =>
  expect(
    healthStatus({
      ...base,
      runtime: {
        ...base.runtime,
        last_success_ms: now - 3600000,
        last_attempt_ms: now,
      },
    }).status,
  ).toBe("DEGRADED"));
