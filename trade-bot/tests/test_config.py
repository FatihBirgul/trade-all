from pathlib import Path

import pytest
from pydantic import ValidationError

from tradebot.config import BotSettings, ManageSettings, RiskSettings, load_settings

ENV = {
    "EXNESS_API_KEY": "exnsk-SECRET-key",
    "EXNESS_PRIVATE_KEY": "SECRET-private",
    "EXNESS_ACCOUNT_ID": "123456",
    "EXNESS_GATEWAY_HOST": "gateway.example",
}


def test_defaults_match_spec():
    risk = RiskSettings()
    assert (risk.risk_pct, risk.max_open_bot, risk.per_symbol, risk.per_currency_side) == (0.5, 3, 1, 2)
    assert (risk.daily_loss_pct, risk.total_loss_pct) == (5, 25)
    manage = ManageSettings()
    assert (manage.be_at_r, manage.partial_at_r, manage.partial_fraction) == (1.0, 2.0, 0.5)
    assert (manage.trail_atr_mult, manage.tp2_r) == (1.0, 3.0)
    bot = BotSettings()
    assert bot.dry_run is True
    assert bot.enabled_symbols is None and bot.enabled_strategies is None
    assert bot.commission_per_lot == 0.0
    settings = load_settings(ENV)
    assert settings.db_path == Path("/var/lib/tradebot/tradebot.db")
    assert settings.api_bind == "127.0.0.1:8090"
    assert settings.exness_ap_host is None
    assert settings.v9_root.name == "trade-ai-unified"


@pytest.mark.parametrize(
    "field,value",
    [("risk_pct", 1.5), ("risk_pct", 0.1), ("max_open_bot", 6), ("max_open_bot", 0),
     ("daily_loss_pct", 11), ("total_loss_pct", 31), ("total_loss_pct", 9),
     ("per_symbol", 2), ("per_currency_side", 3)],
)
def test_out_of_range_rejected(field, value):
    with pytest.raises(ValidationError):
        RiskSettings(**{field: value})


def test_secrets_not_in_repr():
    settings = load_settings(ENV)
    assert "SECRET" not in repr(settings)
    assert "SECRET" not in str(settings)
    assert settings.exness_api_key.get_secret_value() == "exnsk-SECRET-key"


def test_missing_required_env_names_the_variable():
    env = dict(ENV)
    del env["EXNESS_ACCOUNT_ID"]
    with pytest.raises(ValueError, match="EXNESS_ACCOUNT_ID"):
        load_settings(env)


def test_bot_settings_roundtrip_json():
    bot = BotSettings(enabled_symbols={"EURUSD", "BTCUSD"}, dry_run=False)
    again = BotSettings.model_validate_json(bot.model_dump_json())
    assert again == bot
