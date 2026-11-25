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
    [{ min_score: "70" }, "En düşük güven puanı orta eşikten (60) büyük olamaz."],
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
