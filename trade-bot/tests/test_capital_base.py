"""Kayip sinirlarinin tabani (start_capital): canli moda geciste alinir; para yatirma/cekme tabani
kaydirir ve bot kari/zarari sayilmaz."""
import httpx
import pytest

from tests.app_helpers import NOW, build, restart, started
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app
from tradebot.app import BALANCE_SYNC_INTERVAL, BASE_LIVE
from tradebot.config import BotSettings
from tradebot.store.repo import Trade


def base(app):
    state = app.repo.bot_state()
    return state.start_capital, state.start_at


async def go_live_via_api(app):
    token = issue_token(app.repo, now=app.clock["now"])
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test",
                                 headers={"Authorization": f"Bearer {token}"}) as http:
        body = (await http.get("/settings")).json()
        body["dry_run"] = False
        response = await http.put("/settings", json=body)
        assert response.status_code == 200
        return (await http.get("/status")).json()


async def test_dry_run_base_is_provisional_and_live_base_is_taken_at_go_live(tmp_path):
    """Kullanici deneme modunda 1279 USC ile basladi, canliya gecmeden once ~3250 USC'ye tamamladi."""
    app = build(tmp_path, dry_run=True, balance=1279.0, currency="USC")
    await app.bot.start()
    assert base(app) == (1279.0, NOW)
    assert not app.repo.get_setting(BASE_LIVE, False)
    assert "capital_base" not in app.kinds() and app.notifier.sent == []

    app.advance(3600)
    app.fake.balance_operation(1971.0)  # deneme modunda para yatirma
    await app.fake.flush()
    await app.bot.heartbeat()
    assert base(app)[0] == 3250.0  # gecici taban varligi izler
    assert "balance_change" not in app.kinds()  # canli taban yokken kaydirma olayi yok
    assert not app.repo.get_setting(BASE_LIVE, False)

    app.advance(3600)
    live_at = app.clock["now"]
    status = await go_live_via_api(app)
    assert status["dry_run"] is False and status["start_capital"] == 3250.0
    assert base(app) == (3250.0, live_at)  # olcum canliya gecis aninda baslar
    assert app.repo.get_setting(BASE_LIVE) is True
    assert app.kinds().count("capital_base") == 1
    assert app.notifier.kinds() == ["capital_base"] and "3250.00 USC" in app.notifier.sent[0][2]

    # Deneme modundaki para yatirma tabanin icindedir; sonradan gecmisten okununca yeniden eklenmez.
    app.advance(BALANCE_SYNC_INTERVAL + 1)
    await app.bot.heartbeat()
    assert base(app) == (3250.0, live_at)
    assert [op["applied"] for op in app.repo.balance_ops()] == [False]


async def test_go_live_uses_a_fresh_equity_reading(tmp_path):
    """Para az once yatirilmis ve olay akisi bunu henuz tasimamis olabilir: canliya geciste varlik
    broker'dan yeniden okunur."""
    app = build(tmp_path, dry_run=True, balance=1279.0, currency="USC")
    await app.bot.start()
    app.fake.balance_operation(1971.0, event=False)  # olay yok; botun bildigi varlik hala 1279
    assert app.bot.account.equity == 1279.0
    app.advance(60)
    await go_live_via_api(app)
    assert base(app)[0] == 3250.0


async def test_go_live_detected_without_the_api_hook_and_never_twice(tmp_path):
    app = build(tmp_path, dry_run=True, balance=3000.0)
    await app.bot.start()
    app.repo.set_bot_settings(BotSettings(dry_run=False))  # ayar baska bir yoldan degisti
    app.advance(900)
    live_at = app.clock["now"]
    await app.bot.on_bar_close()  # limit kontrolu her taramadan once tabani kurar
    assert base(app) == (3000.0, live_at)

    # Deneme moduna donup yeniden canliya gecmek tabani ve olcum baslangicini SIFIRLAMAZ
    # (aksi halde toplam kayip siniri bir ayar degisikligiyle silinebilirdi).
    app.repo.set_bot_settings(BotSettings(dry_run=True))
    app.fake.balance = 2400.0  # 600 kayip (bot islemleriyle olmus varsayalim)
    app.advance(900)
    await app.bot.reconcile_now()
    await app.bot.heartbeat()
    assert base(app) == (3000.0, live_at)
    app.repo.set_bot_settings(BotSettings(dry_run=False))
    app.advance(900)
    await app.bot.settings_changed()
    await app.bot.heartbeat()
    assert base(app) == (3000.0, live_at)
    assert app.kinds().count("capital_base") == 1


async def test_bot_started_live_takes_its_base_at_start_and_keeps_it_across_restart(tmp_path):
    app = await started(tmp_path)  # dry_run=False ile ilk acilis
    assert base(app) == (10_000.0, NOW) and app.repo.get_setting(BASE_LIVE) is True
    app.fake.balance = 9_000.0
    app.advance(600)
    again = restart(app)
    await again.bot.start()
    assert base(again) == (10_000.0, NOW)
    assert again.kinds().count("capital_base") == 1


async def test_no_base_on_an_empty_account_then_base_after_funding(tmp_path):
    """Canli kurulum: hesap bostu (kesif: bakiye 0). 0 taban yeni islemi ve sinirlari devre disi birakirdi."""
    app = build(tmp_path, dry_run=True, balance=0.0)
    await app.bot.start()
    await app.bot.heartbeat()
    assert not app.repo.bot_state().start_capital
    app.repo.set_bot_settings(BotSettings(dry_run=False))
    await app.bot.settings_changed()
    assert not app.repo.bot_state().start_capital  # bos hesapla canli taban da kurulmaz
    assert not app.repo.get_setting(BASE_LIVE, False)

    app.fake.balance_operation(3000.0)
    await app.fake.flush()
    app.advance(60)
    await app.bot.heartbeat()
    assert base(app) == (3000.0, app.clock["now"]) and app.repo.get_setting(BASE_LIVE) is True
    # Tabandan onceki para yatirma tabana ikinci kez eklenmez.
    app.advance(BALANCE_SYNC_INTERVAL + 1)
    await app.bot.heartbeat()
    assert base(app)[0] == 3000.0


async def test_zero_base_stored_by_an_older_version_is_healed(tmp_path):
    app = await started(tmp_path)
    app.repo.conn.execute("UPDATE bot_state SET start_capital = 0")
    await app.bot.heartbeat()
    assert app.repo.bot_state().start_capital == 10_000.0


@pytest.mark.parametrize("via_event", [True, False])
async def test_deposit_and_withdrawal_shift_the_live_base_exactly_once(tmp_path, via_event):
    app = await started(tmp_path)
    assert base(app) == (10_000.0, NOW)
    app.advance(600)
    deposit = app.fake.balance_operation(2_000.0, event=via_event)
    await app.fake.flush()
    if not via_event:
        assert base(app)[0] == 10_000.0  # olay gelmedi: gecmis taramasi yakalar
        app.advance(BALANCE_SYNC_INTERVAL + 1)
    await app.bot.heartbeat()
    assert base(app) == (12_000.0, NOW)  # olcum baslangici degismez

    # Ayni deal hem olaydan hem gecmisten gelir: tek kez islenir.
    for _ in range(3):
        app.advance(BALANCE_SYNC_INTERVAL + 1)
        await app.bot.heartbeat()
    assert base(app)[0] == 12_000.0
    assert app.kinds().count("balance_change") == 1
    assert app.notifier.kinds() == ["balance_change"] and "Para yatırma" in app.notifier.sent[0][1]

    app.advance(600)
    app.fake.balance_operation(-5_000.0, event=via_event)
    await app.fake.flush()
    app.advance(BALANCE_SYNC_INTERVAL + 1)
    await app.bot.heartbeat()
    assert base(app)[0] == 7_000.0
    ops = app.repo.balance_ops()
    assert [(op["amount"], op["applied"]) for op in ops] == [(2_000.0, True), (-5_000.0, True)]
    assert ops[0]["deal_id"] == deposit

    again = restart(app)  # yeniden baslatma islemleri yeniden uygulamaz
    await again.bot.start()
    again.advance(BALANCE_SYNC_INTERVAL + 1)
    await again.bot.heartbeat()
    assert base(again) == (7_000.0, NOW)


async def test_deposit_is_not_bot_profit_and_withdrawal_is_not_bot_loss(tmp_path):
    """%25 toplam / %5 gunluk sinir yalnizca bot islemlerinin sonucuna bakar."""
    app = await started(tmp_path)
    assert app.bot.bot_pnl() == (0.0, 0.0)
    app.advance(600)
    app.fake.balance_operation(-6_000.0)  # varligin %60'i cekildi: kayip degil
    await app.fake.flush()
    await app.bot.heartbeat()
    summary = await app.bot.on_bar_close()
    state = app.repo.bot_state()
    assert app.bot.bot_pnl() == (0.0, 0.0)
    assert not state.halted and summary.skipped is None
    assert "bot_halted" not in app.kinds() and "daily_limit" not in app.kinds()
    assert state.start_capital == 4_000.0
    status = app.bot.status()
    assert status["pnl_today"] == {"bot": 0.0, "manual": 0.0, "total": 0.0}

    app.fake.balance_operation(50_000.0)  # buyuk para yatirma: kar degil
    await app.fake.flush()
    await app.bot.heartbeat()
    assert app.bot.bot_pnl() == (0.0, 0.0) and app.repo.bot_state().start_capital == 54_000.0


async def test_loss_limits_use_the_shifted_base(tmp_path):
    """Taban 10000 iken 2000 zarar %20'dir (sinir %25). 4000 cekilince taban 6000 olur; ayni zarar %33."""
    app = await started(tmp_path)
    app.advance(60)
    app.repo.upsert_trade(Trade(position_id="9", origin="bot", symbol="EURUSD", side="BUY", volume=0.0,
                                entry=1.1, opened_at=NOW + 10, closed_at=NOW + 60))
    app.repo.add_realized("9", "deal-loss", NOW + 60, -2_000.0)
    await app.bot.heartbeat()
    assert not app.repo.bot_state().halted
    app.advance(600)
    app.fake.balance_operation(-4_000.0)
    await app.fake.flush()
    await app.bot.heartbeat()
    assert app.repo.bot_state().start_capital == 6_000.0
    assert app.repo.bot_state().halted and "bot_halted" in app.kinds()
    assert app.bot.bot_pnl()[1] == -2_000.0  # cekilen tutar zarara eklenmedi


async def test_deposit_scales_the_limits_up_without_hiding_real_losses(tmp_path):
    app = await started(tmp_path)
    app.advance(60)
    app.repo.upsert_trade(Trade(position_id="9", origin="bot", symbol="EURUSD", side="BUY", volume=0.0,
                                entry=1.1, opened_at=NOW + 10, closed_at=NOW + 60))
    app.repo.add_realized("9", "deal-loss", NOW + 60, -2_000.0)
    app.advance(600)
    app.fake.balance_operation(10_000.0)
    await app.fake.flush()
    await app.bot.heartbeat()
    assert app.repo.bot_state().start_capital == 20_000.0
    assert app.bot.bot_pnl()[1] == -2_000.0  # zarar hala sayiliyor; para yatirma onu silmedi
    assert not app.repo.bot_state().halted  # 2000 / 20000 = %10 < %25


async def test_withdrawing_everything_never_leaves_a_negative_base(tmp_path):
    app = await started(tmp_path)
    app.advance(600)
    app.fake.balance_operation(-10_000.0)
    await app.fake.flush()
    await app.bot.heartbeat()
    assert app.repo.bot_state().start_capital == 0.0
    summary = await app.bot.on_bar_close()
    assert summary.opened == 0 and app.fake.calls("POST", "/positions") == []


async def test_balance_event_without_operation_does_not_disturb_orders(tmp_path):
    """Bakiye olayi operation_id tasimaz; emir eslestirmesi bundan etkilenmemeli."""
    app = await started(tmp_path)
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1
    await app.fake.flush()
    trades_before = [(t.position_id, t.origin, t.volume) for t in app.repo.open_trades()]
    app.advance(60)
    app.fake.balance_operation(500.0)
    await app.fake.flush()
    assert [(t.position_id, t.origin, t.volume) for t in app.repo.open_trades()] == trades_before
    assert app.repo.bot_state().start_capital == 10_500.0
    assert "order_rejected" not in app.kinds()
