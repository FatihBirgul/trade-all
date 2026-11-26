import { currentPeriodPnl, periodKey } from "../src/bot/periods";
import { centNote, majorText } from "../src/bot/presentation";

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

test("cent accounts show the major-currency equivalent; other accounts show nothing extra", () => {
  expect(majorText(3000, "USC")).toBe("≈ 30,00 USD");
  expect(majorText(303274, "USC")).toBe("≈ 3.032,74 USD");
  expect(majorText(-360, "USC", true)).toBe("≈ −3,60 USD");
  expect(majorText(1500, "EUC")).toBe("≈ 15,00 EUR");
  expect(majorText(3000, "USD")).toBe("");
  expect(majorText(null, "USC")).toBe("");
  expect(majorText(3000, null)).toBe("");
  expect(centNote("USC")).toBe("Tutarlar USC (cent) cinsindendir: 100 USC = 1 USD.");
  expect(centNote("USD")).toBe("");
});
