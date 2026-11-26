"""Backtest sonrasi kullanici karari (2026-11-26): M15 stratejileri kapali, V9 stratejileri golgede. Bir kez
uygulanir, yalnizca sikilastirir; sonrasinda kullanicinin uygulamadan yaptigi secim korunur."""
from tests.app_helpers import build, restart, started
from tradebot.config import BotSettings, RiskSettings, strategy_mode

M15 = ("tb_ema_pullback_v1", "tb_donchian_breakout_v1", "tb_silver_bullet_v1")
V9 = ("fx_failed_breakout_v6", "fx_confirmed_breakout_v6", "fx_range_reversion_v6", "fx_trend_momentum_v6")


async def test_policy_turns_m15_strategies_off_and_v9_strategies_to_shadow_once(tmp_path):
    app = build(tmp_path, policy=True)
    await app.bot.start()
    settings = app.repo.get_bot_settings()
    assert [strategy_mode(settings, s) for s in M15] == ["off"] * 3
    assert [strategy_mode(settings, s) for s in V9] == ["shadow"] * 4
    assert strategy_mode(settings, "tb_smc_sweep_v1") == "shadow"  # digerleri degismedi
    assert app.kinds().count("strategy_policy") == 1
    # Kullanici sonradan bir stratejiyi yeniden acarsa, yeniden baslatma bunu geri almaz.
    settings.strategy_modes["tb_silver_bullet_v1"] = "shadow"
    app.repo.set_bot_settings(settings)
    again = restart(app, policy=True)
    await again.bot.start()
    assert strategy_mode(again.repo.get_bot_settings(), "tb_silver_bullet_v1") == "shadow"
    assert again.kinds().count("strategy_policy") == 1


async def test_policy_never_loosens_a_stricter_choice_and_no_v9_order_is_sent_afterwards(tmp_path):
    app = build(tmp_path, policy=True)
    app.repo.set_bot_settings(BotSettings(dry_run=False, risk=RiskSettings(max_spread_stop_pct=25),
                                          strategy_modes={"fx_range_reversion_v6": "off"}))
    app = await started(tmp_path, fake=app.fake, clock=app.clock, policy=True)
    settings = app.repo.get_bot_settings()
    assert strategy_mode(settings, "fx_range_reversion_v6") == "off"  # kapali olan golgeye "acilmaz"
    assert strategy_mode(settings, "fx_trend_momentum_v6") == "shadow"
    before = len(app.fake.requests)
    summary = await app.bot.on_bar_close()
    assert summary.candidates >= 1 and summary.opened == 0
    assert not [r for r in app.fake.requests[before:] if r[0] == "POST"]  # canli modda bile emir gitmedi
