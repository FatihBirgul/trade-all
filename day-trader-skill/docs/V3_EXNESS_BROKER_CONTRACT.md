# Exness Cent broker sözleşmesi durumu

10 Kasım 2026. Mevcut `MT5_SYMBOL_MAP` dört canonical sembol için açık alias kabul eder: `XAUUSDc`, `EURUSDc`, `GBPUSDc`, `USDJPYc`. `MT5Provider` exact MT5 symbol lookup, select, temel/base-profit currency, tick/point, kontrat, volume grid, stop level, trade mode, hesap para birimi ve quote zamanını okur. Dört alias sentetik terminal ile test edildi; gerçek terminal metadata'sı okunmadı.

Mevcut `MT5_BROKER_HOURS` politika kaynağı operatör beyanıdır. MT5 Python SDK'sının kanıtlanmamış session metadata'sı icat edilmedi. Saatlerin timezone, haftalık pencere ve date override alanları vardır; kaynak URL, effective date, broker sunucu UTC offset geçmişi ve bağımsız doğrulama alanları henüz yoktur. Bu nedenle Exness-MT5Real50 için XAUUSDc 21:45-23:00 gözlemi, hafta sonu/holiday/DST çizelgesi ve tüm dört sembolün gerçek seansları UNVERIFIED. Açık pencere bilinmiyorsa manuel plan verilmez.

Gerçek doğrulama için hesap/sunucu kimliğini ifşa etmeden read-only terminal_info, symbol_info, account currency, symbol_info_tick, kapalı M15/H4 bar zamanları ve `order_calc_profit` sonuçları ayrı bir demo terminalde kaydedilmeli. REAL hesaba bağlantı veya emir bu teslimde yoktur.
