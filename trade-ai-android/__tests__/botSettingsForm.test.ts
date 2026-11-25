import { draftFrom, planChanges, strategyName } from "../src/bot/settingsForm";
import type { BotSettings } from "../src/bot/types";

const settings = (): BotSettings => ({
  risk: { risk_pct: 0.5, max_open_bot: 3, per_symbol: 1, per_currency_side: 2, daily_loss_pct: 5, total_loss_pct: 25 },
  news: { enabled: true, window_minutes: 30 },
  fusion: { enabled: true, min_score: 40, mid_score: 60, high_score: 80, weights: { mtf: 2 } },
  dry_run: true,
  strategy_modes: { fx_range_reversion_v6: "shadow" },
  enabled_symbols: null,
});

test("unchanged draft produces no changes", () => {
  const plan = planChanges(settings(), draftFrom(settings()));
  expect(plan).toMatchObject({ ok: true, changes: [], riskier: false });
});

test("only changed fields are applied and untouched fields survive", () => {
  const draft = { ...draftFrom(settings()), risk_pct: "0,25", news_window: "45" };
  const plan = planChanges(settings(), draft);
  if (!plan.ok) throw new Error(plan.error);
  expect(plan.changes).toEqual([
    { label: "İşlem başı risk", from: "0,5%", to: "0,25%", riskier: false },
    { label: "Haber penceresi", from: "30 dk", to: "45 dk", riskier: false },
  ]);
  expect(plan.riskier).toBe(false);
  // Sunucudan yeni okunan (başka bir yerden değişmiş) ayarlara uygulanır: diğer alanlar korunur.
  const fresh = settings();
  fresh.risk.max_open_bot = 2;
  fresh.strategy_modes = { fx_trend_momentum_v6: "shadow" };
  const applied = plan.apply(fresh);
  expect(applied.risk).toMatchObject({ risk_pct: 0.25, max_open_bot: 2, daily_loss_pct: 5 });
  expect(applied.news.window_minutes).toBe(45);
  expect(applied.strategy_modes).toEqual({ fx_trend_momentum_v6: "shadow" });
  expect(applied.fusion.weights).toEqual({ mtf: 2 });
});

test("changes that raise risk are flagged", () => {
  const cases: [Partial<ReturnType<typeof draftFrom>>, boolean][] = [
    [{ risk_pct: "1" }, true],
    [{ max_open_bot: "5" }, true],
    [{ daily_loss_pct: "10" }, true],
    [{ total_loss_pct: "30" }, true],
    [{ total_loss_pct: "10" }, false],
    [{ news_window: "5" }, true],
    [{ news_enabled: false }, true],
    [{ fusion_enabled: false }, true],
    [{ min_score: "20" }, true],
    [{ min_score: "55" }, false],
  ];
  for (const [change, riskier] of cases) {
    const plan = planChanges(settings(), { ...draftFrom(settings()), ...change });
    expect(plan.ok && plan.riskier).toBe(riskier);
  }
});

test("out of range or malformed values are rejected with the allowed range", () => {
  for (const [change, message] of [
    [{ risk_pct: "2" }, "İşlem başı risk: 0,25 ile 1 arasında bir sayı girin."],
    [{ risk_pct: "0.1" }, "İşlem başı risk: 0,25 ile 1 arasında bir sayı girin."],
    [{ risk_pct: "" }, "İşlem başı risk: 0,25 ile 1 arasında bir sayı girin."],
    [{ risk_pct: "1e0" }, "İşlem başı risk: 0,25 ile 1 arasında bir sayı girin."],
    [{ max_open_bot: "2,5" }, "Aynı anda açık bot işlemi: 1 ile 5 arasında tam sayı girin."],
    [{ total_loss_pct: "50" }, "Toplam kayıp sınırı: 10 ile 30 arasında bir sayı girin."],
    [{ news_window: "0" }, "Haber penceresi: 5 ile 120 arasında tam sayı girin."],
    [{ min_score: "70" }, "Güven eşikleri sıralı olmalı: en düşük ≤ orta ≤ yüksek."],
  ] as const) {
    expect(planChanges(settings(), { ...draftFrom(settings()), ...change })).toEqual({ ok: false, error: message });
  }
});

test("the form never touches dry run or strategy modes", () => {
  const plan = planChanges(settings(), { ...draftFrom(settings()), risk_pct: "1" });
  if (!plan.ok) throw new Error(plan.error);
  const applied = plan.apply(settings());
  expect(applied.dry_run).toBe(true);
  expect(applied.strategy_modes).toEqual({ fx_range_reversion_v6: "shadow" });
});

test("strategy names", () => {
  expect(strategyName("tb_ema_pullback_v1")).toBe("EMA geri çekilme (yeni)");
  expect(strategyName("bilinmeyen_x")).toBe("bilinmeyen_x");
});

test("apply refuses to write when the server value differs from what the confirmation showed", () => {
  // Ekran 0,5 → 0,75 gösterdi; sunucuda değer bu arada 1 olmuş: kullanıcı yanlış karşılaştırmayı onayladı.
  const plan = planChanges(settings(), { ...draftFrom(settings()), risk_pct: "0,75", news_enabled: false });
  if (!plan.ok) throw new Error(plan.error);
  const fresh = settings();
  fresh.risk.risk_pct = 1;
  expect(() => plan.apply(fresh)).toThrow(/sunucuda değişmiş/);
  const other = settings();
  other.news.enabled = false;
  expect(() => plan.apply(other)).toThrow(/sunucuda değişmiş/);
  expect(plan.apply(settings()).risk.risk_pct).toBe(0.75);
});

const withManage = (): BotSettings => ({
  ...settings(),
  manage: { be_enabled: true, partial_enabled: true, trail_enabled: true, be_at_r: 1 },
});
const UNIVERSE = ["BTCUSD", "EURUSD", "GBPUSD", "XAUUSD"];

test("score thresholds must stay ordered and lowering one is flagged as riskier", () => {
  const base = draftFrom(withManage());
  expect(planChanges(withManage(), { ...base, mid_score: "30" })).toMatchObject({ ok: false }); // orta < en düşük (40)
  expect(planChanges(withManage(), { ...base, high_score: "50" })).toMatchObject({ ok: false }); // yüksek < orta (60)
  expect(planChanges(withManage(), { ...base, mid_score: "101" })).toMatchObject({ ok: false });
  const plan = planChanges(withManage(), { ...base, mid_score: "50", high_score: "90" });
  if (!plan.ok) throw new Error(plan.error);
  expect(plan.changes).toEqual([
    { label: "Orta güven eşiği (altı yarım lot)", from: "60", to: "50", riskier: true },
    { label: "Yüksek güven eşiği (üstü tam lot)", from: "80", to: "90", riskier: false },
  ]);
  const saved = plan.apply(withManage());
  expect(saved.fusion).toMatchObject({ min_score: 40, mid_score: 50, high_score: 90, weights: { mtf: 2 } });
});

test("switching a stop stage off is riskier and keeps the other manage values", () => {
  const plan = planChanges(withManage(), { ...draftFrom(withManage()), trail_enabled: false, be_enabled: false });
  if (!plan.ok) throw new Error(plan.error);
  expect(plan.riskier).toBe(true);
  expect(plan.changes.map((c) => [c.label, c.to, c.riskier])).toEqual([
    ["Başa baş stopu (1R’de)", "Kapalı", true],
    ["İz süren stop", "Kapalı", true],
  ]);
  expect(plan.apply(withManage()).manage).toEqual({ be_enabled: false, partial_enabled: true, trail_enabled: false, be_at_r: 1 });
  // Eski sunucu (manage alanı yok): anahtarlar açık görünür, değiştirmek açık bir hatayla durur.
  expect(draftFrom(settings()).trail_enabled).toBe(true);
  const old = planChanges(settings(), { ...draftFrom(settings()), trail_enabled: false });
  if (!old.ok) throw new Error(old.error);
  expect(() => old.apply(settings())).toThrow(/desteklemiyor/);
});

test("symbol selection: old → new counts, all selected is stored as null, empty is refused", () => {
  const base = draftFrom(withManage());
  expect(base.symbols).toBeNull();
  expect(planChanges(withManage(), { ...base, symbols: [] }, UNIVERSE)).toMatchObject({ ok: false });
  expect(planChanges(withManage(), { ...base, symbols: [...UNIVERSE].reverse() }, UNIVERSE)).toMatchObject({ ok: true, changes: [] });
  const plan = planChanges(withManage(), { ...base, symbols: ["XAUUSD", "EURUSD"] }, UNIVERSE);
  if (!plan.ok) throw new Error(plan.error);
  expect(plan.changes).toEqual([
    { label: "Açık semboller", from: "Hepsi", to: "2 (kapanan: BTCUSD, GBPUSD)", riskier: false },
  ]);
  expect(plan.apply(withManage()).enabled_symbols).toEqual(["EURUSD", "XAUUSD"]);
  // Sunucudaki liste bu arada değişmişse yazılmaz.
  expect(() => plan.apply({ ...withManage(), enabled_symbols: ["BTCUSD"] })).toThrow(/sunucuda değişmiş/);

  const limited = { ...withManage(), enabled_symbols: ["XAUUSD"] };
  const reopen = planChanges(limited, { ...draftFrom(limited), symbols: [...UNIVERSE] }, UNIVERSE);
  if (!reopen.ok) throw new Error(reopen.error);
  expect(reopen.changes[0]).toMatchObject({ from: "1", to: "Hepsi (açılan: BTCUSD, EURUSD, GBPUSD)" });
  expect(reopen.apply({ ...withManage(), enabled_symbols: ["XAUUSD"] }).enabled_symbols).toBeNull();
});
