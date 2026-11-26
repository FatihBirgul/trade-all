import { checkLevel, parsePrice } from "../src/bot/levels";
import { previewMatches, resultNotice, sameRequest } from "../src/bot/manualTrade";

test("prices are parsed strictly", () => {
  expect(parsePrice(" 1,0972 ")).toBe(1.0972);
  expect(parsePrice("1.0972")).toBe(1.0972);
  expect(parsePrice("")).toBeUndefined();
  for (const bad of ["abc", "-1", "0", "1.2.3", "1e5", "64.800,5"]) expect(parsePrice(bad)).toBeNull();
});

test("a stop or target on the wrong side, or absurdly far, is refused", () => {
  const buy = { side: "BUY" as const, sl: 2023.29, price: 2023.9, entry: 2024.1 };
  expect(checkLevel("sl", 2030, buy).ok).toBe(false); // alışta stop fiyatın üstünde olamaz
  expect(checkLevel("tp", 2020, buy).ok).toBe(false);
  expect(checkLevel("sl", 20.23, buy).ok).toBe(false); // yazım hatası: fiyattan çok uzak
  expect(checkLevel("sl", 2023.5, buy)).toEqual({ ok: true, widens: false });
  expect(checkLevel("sl", 2022, buy)).toEqual({ ok: true, widens: true }); // stop uzaklaşıyor
  const sell = { side: "SELL" as const, sl: 2034.1, price: 2032.25, entry: 2031.4 };
  expect(checkLevel("sl", 2030, sell).ok).toBe(false);
  expect(checkLevel("sl", 2036, sell)).toEqual({ ok: true, widens: true });
  expect(checkLevel("tp", 2025, sell)).toEqual({ ok: true, widens: false });
  expect(checkLevel("sl", 2030, { ...buy, price: null }).ok).toBe(false); // fiyat yoksa girişe göre
});

test("a preview is only valid for the exact request it was made for", () => {
  const trade = { symbol: "EURUSD", side: "BUY" as const, sl_distance: 0.002 };
  expect(sameRequest(trade, { ...trade })).toBe(true);
  expect(sameRequest(trade, { ...trade, sl_distance: 0.003 })).toBe(false);
  expect(sameRequest(trade, { ...trade, lots: 0.1 })).toBe(false);
  expect(sameRequest(trade, { ...trade, risk_pct: 1 })).toBe(false);
  expect(previewMatches({ symbol: "EURUSD", side: "SELL" } as never, trade)).toBe(false);
});

test("a 200 reply is not reported as success when the order was rejected or is unknown", () => {
  expect(resultNotice({ state: "REJECTED", lots: 0.1 }, "0,1").bad).toBe(true);
  expect(resultNotice({ state: null, lots: 0.1 }, "0,1").bad).toBe(true);
  expect(resultNotice({ state: "UNKNOWN", lots: 0.1 }, "0,1").bad).toBe(true);
  expect(resultNotice({ state: "FILLED", lots: 0.1 }, "0,1")).toEqual({ text: expect.stringContaining("Emir gönderildi"), bad: false });
});
