"""Enstruman katalogu ve islem evreni (spec §6.1)."""

from __future__ import annotations

import dataclasses
import logging

from ..exness import schema

from ..exness.errors import ExnessAuthError, ExnessError, ExnessRateLimited
from ..exness.schema import Instrument

log = logging.getLogger(__name__)

CRYPTO_UNIVERSE = frozenset({"BTCUSD", "ETHUSD"})


def in_universe(instrument: Instrument) -> bool:
    """Forex + metal + (BTC, ETH)/USD. Hisse, endeks, enerji ve diger kriptolar evren disidir."""
    if not instrument.tradable:
        return False
    if instrument.kind in ("forex", "metal"):
        return True
    return instrument.kind == "crypto" and instrument.symbol in CRYPTO_UNIVERSE


class InstrumentCatalog:
    def __init__(self, client):
        self._client = client
        self._by_symbol: dict[str, Instrument] = {}
        self._by_broker: dict[str, Instrument] = {}

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
        return errors

    def update(self, instrument: Instrument) -> None:
        current = self._by_symbol.get(instrument.symbol)
        if current is not None and current.broker_symbol != instrument.broker_symbol:
            # Ayni kanonik ada iki broker adi duserse ilk gorulen kalir; sessizce degistirme.
            log.warning("katalog: %s icin ikinci broker adi yok sayildi (%s)", instrument.symbol,
                        instrument.broker_symbol)
            return
        if current is not None and (instrument.tick_size <= 0 or instrument.contract_size <= 0):
            # Eksik bir guncelleme (or. kismi olay yuku) bilinen sozlesme bilgisini silmesin:
            # acik pozisyonun yonetimi ve kapatilmasi bu bilgilere bagli. Yalnizca isleme kapat.
            instrument = dataclasses.replace(current, tradable=False)
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
