import {
  emptyPortfolio,
  gatewayOrigin,
  lastScanText,
  money,
  safeDecision,
} from "../src/domain/safety";
import { demoAnalysis } from "../src/demo";
import {
  directionText,
  reasonText,
  technicalStatusText,
  paperStatusText,
  transactionText,
  userErrorText,
} from "../src/domain/presentation";
import example from "../docs/backend/v2_examples/analysis.json";
import type { Analysis } from "../src/domain/safety";
test("independent virtual accounts start at 10000 decimal USDT", () => {
  const auto = emptyPortfolio("AUTO");
  const manual = emptyPortfolio("MANUAL");
  auto.cash_quote = "9";
  expect(manual.cash_quote).toBe("10000");
  expect(manual.portfolio_id).toBe("MANUAL");
});
test("money formatting never uses binary floating ledger arithmetic", () => {
  expect(money("9007199254740993.123456")).toBe("9.007.199.254.740.993,12");
  expect(money(null)).toBe("—");
});
test.each([
  "http://api.example.com",
  "https://127.0.0.1",
  "https://localhost",
  "https://user:secret@host.example",
  "https://host.example/path",
  "https://host.example?token=x",
])("reject unsafe gateway %s", (url) => {
  expect(() => gatewayOrigin(url)).toThrow();
});
test("HTTPS origin accepted", () =>
  expect(gatewayOrigin("https://gateway.example.com/")).toBe(
    "https://gateway.example.com",
  ));
test("geçersiz gateway adresi Türkçe hata verir", () => {
  expect(() => gatewayOrigin("")).toThrow(
    "Geçerli bir HTTPS gateway adresi girin.",
  );
  expect(() => gatewayOrigin("gateway.example.com")).toThrow(
    "Geçerli bir HTTPS gateway adresi girin.",
  );
});
test("tarayıcı ilk taramadan önce zaman uydurmaz", () => {
  expect(lastScanText(null)).toBe("Henüz tarama yapılmadı");
  expect(lastScanText(0)).toBe("Henüz tarama yapılmadı");
});
test("sistem hataları kullanıcıya Türkçe gösterilir", () => {
  expect(userErrorText(new TypeError("Invalid URL: abc"))).toBe(
    "İşlem tamamlanamadı.",
  );
  expect(
    userErrorText(new Error("Network request failed"), "Bağlantı kurulamadı."),
  ).toBe("Bağlantı kurulamadı.");
  expect(userErrorText(new Error("Geçerli adres girin."))).toBe(
    "Geçerli adres girin.",
  );
});
test("DEMO cannot emit a trading signal", () => {
  const started = Date.now();
  const a = demoAnalysis("BTCUSDT", "1H", "MANUAL", "demo");
  expect(safeDecision(a)).toBe("WAIT");
  expect(a.levels).toBeNull();
  expect(a.auto_order_id).toBeNull();
  expect(a.price).toBeNull();
  expect(a.created_at_ms).toBeGreaterThanOrEqual(started);
});

test("bilinen analiz durumları Türkçe, bilinmeyen kodlar açık gösterilir", () => {
  expect(reasonText("local_demo_no_market_data")).toContain(
    "piyasa verisi yok",
  );
  expect(reasonText("new_backend_reason")).toBe(
    "Neden kodu: new_backend_reason",
  );
  expect(directionText("bullish")).toBe("Yükseliş");
  expect(technicalStatusText("available")).toBe("Hesaplandı");
  expect(paperStatusText("pending")).toBe("Bekliyor");
  expect(transactionText("entry")).toContain("açılışı");
});
test("nested candidates cannot override WAIT or missing quality", () => {
  const a = example as Analysis;
  expect(safeDecision({ ...a, direction: "WAIT" })).toBe("WAIT");
  expect(safeDecision({ ...a, quality: {} })).toBe("WAIT");
  expect(safeDecision({ ...a, levels: null })).toBe("WAIT");
  expect(safeDecision({ ...a, risk: {} })).toBe("WAIT");
});

test("süresi dolmuş, gelecekteki fiyat ve bozuk seviyeler WAIT olur", () => {
  const now = Date.now();
  const a = {
    ...example,
    price_time_ms: now - 1000,
    expires_at_ms: now + 1000,
  } as Analysis;
  expect(safeDecision(a, now)).toBe("bullish");
  expect(safeDecision(a, now + 1000)).toBe("WAIT");
  expect(safeDecision({ ...a, price_time_ms: now + 1 }, now)).toBe("WAIT");
  for (const price of ["0", "-1", "NaN", "Infinity", "abc"]) {
    expect(safeDecision({ ...a, price }, now)).toBe("WAIT");
  }
  expect(
    safeDecision({ ...a, levels: { ...a.levels!, target_1: "NaN" } }, now),
  ).toBe("WAIT");
});
