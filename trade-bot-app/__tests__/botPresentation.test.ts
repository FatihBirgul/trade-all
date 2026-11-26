import { agoText, amountText, botStateText, pnlText, pnlTone, priceText, rText } from "../src/bot/presentation";

const base = { halted: false, halt_reason: null, stopped: false, stream_connected: true, dry_run: false };

test("state text priority", () => {
  expect(botStateText(base)).toEqual({ label: "Çalışıyor", tone: "ok" });
  expect(botStateText({ ...base, dry_run: true })).toEqual({
    label: "Deneme modu: bot emir göndermiyor",
    tone: "warn",
  });
  expect(botStateText({ ...base, dry_run: true, stream_connected: false }).label).toBe("Exness bağlantısı yok");
  expect(botStateText({ ...base, dry_run: true, stream_connected: false, stopped: true }).label).toBe("Durduruldu");
  expect(
    botStateText({ ...base, stopped: true, stream_connected: false, halted: true, halt_reason: null }),
  ).toEqual({ label: "Durdu: toplam kayıp sınırı", tone: "bad" });
  expect(botStateText({ ...base, halted: true, halt_reason: "toplam kayıp sınırı (%25) aşıldı" }).label).toBe(
    "Durdu: toplam kayıp sınırı (%25) aşıldı",
  );
});

test("pnl text always carries a sign and currency", () => {
  expect(pnlText(12.5, "USC")).toBe("+12,50 USC");
  expect(pnlText(-1234.567, "USC")).toBe("−1.234,57 USC");
  expect(pnlText(0, "USC")).toBe("0,00 USC");
  expect(pnlText(-0.001, "USC")).toBe("0,00 USC");
  expect(pnlText(null, "USC")).toBe("—");
  expect(pnlText(Number.NaN)).toBe("—");
  expect(pnlTone(3)).toBe("ok");
  expect(pnlTone(-3)).toBe("bad");
  expect(pnlTone(0.001)).toBeNull();
  expect(pnlTone(null)).toBeNull();
});

test("amount and price text", () => {
  expect(amountText(3012.5, "USC")).toBe("3.012,50 USC");
  expect(amountText(null, "USC")).toBe("—");
  expect(priceText(1.0972)).toBe("1,0972");
  expect(priceText(2385.5)).toBe("2385,5");
  expect(priceText(null)).toBe("—");
});

test("ago text", () => {
  expect(agoText(null, 1000)).toBe("henüz yok");
  expect(agoText(990, 1000)).toBe("az önce");
  expect(agoText(1000 - 125, 1000)).toBe("2 dk önce");
  expect(agoText(1000 - 7300, 1000)).toBe("2 sa önce");
  expect(agoText(1000 - 200000, 1000)).toBe("2 gün önce");
  expect(agoText(1010, 1000)).toBe("az önce"); // saat farkı negatif süre göstermez
});

test("r multiple text never shows a signed zero", () => {
  expect(rText(1.25)).toBe("+1,25R");
  expect(rText(-0.45)).toBe("−0,45R");
  expect(rText(-0.001)).toBe("0R");
  expect(rText(0)).toBe("0R");
  expect(rText(null)).toBe("");
});
