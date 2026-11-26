import { currentPeriodPnl, periodKey } from "../src/bot/periods";

const at = (iso: string) => Date.parse(iso) / 1000;

test("keys match the server buckets (UTC day, ISO week, month)", () => {
  expect(periodKey("day", at("2027-01-15T10:00:00Z"))).toBe("2027-01-15");
  expect(periodKey("month", at("2027-01-15T10:00:00Z"))).toBe("2027-01");
  expect(periodKey("week", at("2027-01-15T10:00:00Z"))).toBe("2027-W02");
  expect(periodKey("week", at("2026-11-26T12:00:00Z"))).toBe("2026-W48");
  // Yıl sınırı: 1 Ocak 2027 Cuma, ISO'ya göre 2026'nın 53. haftasındadır; 31 Aralık 2024 ise 2025'in 1. haftası.
  expect(periodKey("week", at("2027-01-01T00:00:00Z"))).toBe("2026-W53");
  expect(periodKey("week", at("2024-12-31T23:59:59Z"))).toBe("2025-W01");
  expect(periodKey("day", at("2027-01-15T23:59:59Z"))).toBe("2027-01-15"); // telefonun saat dilimi etkilemez
});

test("the current period comes from its bucket, never from the all-time total", () => {
  const periods = { bot: [], manual: [], all: [{ period: "2027-W01", pnl: 400 }, { period: "2027-W02", pnl: 100 }] };
  expect(currentPeriodPnl({ period: "week", periods }, at("2027-01-15T10:00:00Z"))).toBe(100);
  expect(currentPeriodPnl({ period: "week", periods }, at("2027-01-22T10:00:00Z"))).toBe(0); // bu hafta işlem yok
});
