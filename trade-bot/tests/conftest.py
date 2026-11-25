import pytest


@pytest.fixture(autouse=True)
def _v9_only_unless_testing_custom_strategies(request, monkeypatch):
    """Yeni (V9 disi) stratejiler varsayilan olarak golgede calisir ve ayni piyasa verisinde ek aday uretir.
    Genel testler V9 akisini olcer; yeni stratejiler yalnizca kendi test dosyasinda etkindir."""
    if request.module.__name__.endswith("test_custom_strategies"):
        return
    from tradebot.signals import custom

    monkeypatch.setattr(custom, "evaluate", lambda *args, **kwargs: [])
