"""Enstruman katalogu ve islem evreni (spec §6.1)."""

from __future__ import annotations

import logging
from dataclasses import replace

from ..exness import schema

from ..exness.errors import ExnessAuthError, ExnessError, ExnessRateLimited
from ..exness.schema import Instrument

log = logging.getLogger(__name__)

CRYPTO_UNIVERSE = frozenset({"BTCUSD", "ETHUSD"})


def in_family(instrument: Instrument) -> bool:
    """Evrenin UYESI mi (o an isleme acik olsun olmasin)? Forex + metal + (BTC, ETH)/USD; sozlesme bilgisi tam."""
    if not instrument.listed:
        return False
    if instrument.kind in ("forex", "metal"):
        return True
    return instrument.kind == "crypto" and instrument.symbol in CRYPTO_UNIVERSE


def in_universe(instrument: Instrument) -> bool:
    """Su an taranabilir / islem acilabilir: evrenin uyesi VE broker'da islem kipi acik."""
    return instrument.tradable and in_family(instrument)


class InstrumentCatalog:
    def __init__(self, client):
        self._client = client
        self._by_symbol: dict[str, Instrument] = {}
        self._by_broker: dict[str, Instrument] = {}
        self.errors: dict[str, str] = {}  # son okumada alinamayan enstrumanlar {broker_adi: neden}

    async def refresh(self) -> dict[str, str]:
        """Tum enstruman kosullarini ceker. Tek tek hatalar {broker_adi: neden} olarak doner."""
        account_id = self._client.account_id
        names = schema.parse_instrument_names(await self._client.get(schema.instruments_path(account_id)))
        errors: dict[str, str] = {}
        for name in names:
            try:
                raw = await self._client.get(schema.instrument_path(account_id, name))
                self.update(schema.parse_instrument(raw))
            except (ExnessRateLimited, ExnessAuthError):
                raise  # limit ya da kimlik hatasinda kalan enstrumanlar icin istek gondermeye devam etme
            except (ExnessError, ValueError) as exc:
                errors[name] = f"{type(exc).__name__}: {exc}"
        if errors:
            log.warning("katalog: %d enstruman okunamadi", len(errors))
        self.errors = dict(errors)
        return errors

    async def recheck(self, broker_symbols: list[str]) -> None:
        """Verilen enstrumanlari broker'dan yeniden okur (isleme kapali gorunen ya da okunamamis olanlar icin).
        REST yaniti tam kayittir: olay akisindan gelmis eksik/eski bir durumu duzeltir."""
        account_id = self._client.account_id
        for name in broker_symbols:
            try:
                raw = await self._client.get(schema.instrument_path(account_id, name))
                self.update(schema.parse_instrument(raw))
                self.errors.pop(name, None)
            except (ExnessRateLimited, ExnessAuthError):
                raise
            except (ExnessError, ValueError) as exc:
                self.errors[name] = f"{type(exc).__name__}: {exc}"

    def update(self, instrument: Instrument) -> None:
        current = self._by_symbol.get(instrument.symbol)
        if current is not None and current.broker_symbol != instrument.broker_symbol:
            # Ayni kanonik ada iki broker adi duserse ilk gorulen kalir; sessizce degistirme.
            log.warning("katalog: %s icin ikinci broker adi yok sayildi (%s)", instrument.symbol,
                        instrument.broker_symbol)
            return
        if current is not None and (instrument.tick_size <= 0 or instrument.contract_size <= 0
                                    or (current.listed and not instrument.listed)):
            # Eksik bir guncelleme (or. kismi olay yuku) bilinen sozlesme bilgisini silmesin: acik
            # pozisyonun yonetimi ve kapatilmasi bu bilgilere bagli. Guncelleme yok sayilir; tam bilgi
            # bir sonraki katalog yenilemesinde gelir.
            log.warning("katalog: %s icin eksik guncelleme yok sayildi", instrument.symbol)
            if instrument.trade_mode not in (None, "enabled") and current.broker_symbol == instrument.broker_symbol:
                # Eksik ileti bir KAPANMA bildiriyorsa o kisim uygulanir (kapali tarafa hata): sozlesme bilgisi
                # korunur, sembol isleme kapali sayilir; tam kayit bir sonraki yeniden okumada gelir.
                closed = replace(current, tradable=False, trade_mode=instrument.trade_mode)
                self._by_symbol[closed.symbol] = closed
                self._by_broker[closed.broker_symbol] = closed
            return
        self._by_symbol[instrument.symbol] = instrument
        self._by_broker[instrument.broker_symbol] = instrument

    def get(self, symbol: str) -> Instrument:
        return self._by_symbol[symbol]

    def by_broker(self, broker_symbol: str) -> Instrument | None:
        return self._by_broker.get(broker_symbol)

    def all(self) -> list[Instrument]:
        return sorted(self._by_symbol.values(), key=lambda i: i.symbol)

    def as_mapping(self) -> dict[str, Instrument]:
        return dict(self._by_symbol)

    def universe(self, enabled: set[str] | None = None) -> list[Instrument]:
        return [i for i in self.all() if in_universe(i) and (enabled is None or i.symbol in enabled)]

    def members(self) -> list[Instrument]:
        """Evrenin butun uyeleri: o an isleme kapali olanlar dahil (ayar listesi, backtest, eksik sembol uyarisi)."""
        return [i for i in self.all() if in_family(i)]
