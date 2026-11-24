import { ScannerJournal } from "../src/api/scannerJournal";
import { ApiError, createApi } from "../src/api/client";
import type { IntentStorage } from "../src/api/intent";
function storage() {
  const rows = new Map<string, string>();
  return {
    getItem: async (k: string) => rows.get(k) ?? null,
    setItem: async (k: string, v: string) => {
      rows.set(k, v);
    },
    removeItem: async (k: string) => {
      rows.delete(k);
    },
  };
}
type API = ReturnType<typeof createApi>;
test("completed server jobs after lost response reconcile on restart with no second POST", async () => {
  const saved = storage();
  let advanced = false;
  const tick = jest.fn(async () => {
    advanced = true;
    throw new ApiError("NETWORK", true);
  });
  const api = {
    scanner: async () => ({
      last_tick_ms: advanced ? 200 : 100,
      lease_id: null,
      last_error: null,
    }),
    jobs: async () =>
      advanced
        ? [
            { job_id: "a", status: "completed", started_at_ms: 200 },
            { job_id: "b", status: "completed", started_at_ms: 200 },
          ]
        : [],
    tick,
  } as unknown as API;
  await expect(
    new ScannerJournal(saved, "origin|device|AUTO").execute(api),
  ).rejects.toMatchObject({ uncertain: true });
  const reopened = new ScannerJournal(saved, "origin|device|AUTO");
  await expect(reopened.execute(api)).rejects.toThrow("bekleyen");
  const result = await reopened.reconcile(api);
  expect(result.confirmed).toBe(true);
  expect(result.message).toContain("2 tamamlanan");
  expect(tick).toHaveBeenCalledTimes(1);
  expect(await reopened.pending()).toBeNull();
});
test("running, unreadable and wrong-scope outcomes retain pending and never resend", async () => {
  const saved = storage(),
    tick = jest.fn(async () => {
      throw new ApiError("UPSTREAM_TIMEOUT", true);
    });
  let started = false;
  const api = {
    scanner: async () => ({
      last_tick_ms: started ? 200 : 100,
      lease_id: started ? "lease" : null,
      last_error: null,
    }),
    jobs: async () => [],
    tick,
  } as unknown as API;
  const journal = new ScannerJournal(saved, "origin|device|AUTO");
  await expect(journal.execute(api)).rejects.toBeInstanceOf(ApiError);
  started = true;
  expect((await journal.reconcile(api)).confirmed).toBe(false);
  expect(await journal.pending()).not.toBeNull();
  await expect(
    new ScannerJournal(saved, "other|device|AUTO").reconcile(api),
  ).rejects.toThrow("başka");
  expect(tick).toHaveBeenCalledTimes(1);
});
test("storage failure prevents tick; completed two-job JSON is accepted with bounded 50s client timeout", async () => {
  const tick = jest.fn();
  const broken = {
    getItem: async () => null,
    setItem: async () => {
      throw new Error("disk");
    },
    removeItem: async () => {},
  } as IntentStorage;
  await expect(
    new ScannerJournal(broken, "scope").execute({
      scanner: async () => ({ last_tick_ms: null, lease_id: null }),
      jobs: async () => [],
      tick,
    } as unknown as API),
  ).rejects.toThrow("disk");
  expect(tick).not.toHaveBeenCalled();
  jest.useFakeTimers();
  const timer = jest.spyOn(global, "setTimeout");
  try {
    const result = {
      status: "completed",
      reason: null,
      jobs: ["BTCUSDT", "ETHUSDT"].map((symbol, i) => ({
        job_id: String(i),
        symbol,
        timeframe: "1H",
        closed_bar_ms: 100,
        status: "completed",
        started_at_ms: 101,
        analysis_id: "a".repeat(64),
        reason: null,
      })),
    };
    const api = createApi(
      { origin: "https://pc.example.ts.net", session: "controlled-test" },
      jest.fn().mockResolvedValue({ ok: true, json: async () => result }),
    );
    await expect(api.tick()).resolves.toEqual(result);
    expect(timer).toHaveBeenCalledWith(expect.any(Function), 50000);
  } finally {
    timer.mockRestore();
    jest.useRealTimers();
  }
});
