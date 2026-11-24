# Bakiye ve risk kaynağı

V5 yanıtında ek `risk_balance_source` alanı vardır: `NOT_PROVIDED`, `CALLER_SUPPLIED_HYPOTHETICAL` veya `BROKER_VERIFIED_DEMO`. Doğrudan Python/fixture hesabına verilen bakiye varsayımsaldır. MT5 manuel API yolunda DEMO preflight geçerse istek gövdesindeki `balance` lot hesabında kullanılmaz; SDK `account_info().balance` kullanılır ve kaynak `BROKER_VERIFIED_DEMO` olur. PWA'nın sabit 10.000 değeri gerçek bakiye gibi kabul edilmez. Hesap para birimi ayrı `account_currency` alanında, risk ve broker profit aynı hesap biriminde tutulur.

Gerçek DEMO preflight olmadığı için bu davranış fixture ile doğrulandı; canlı balance veya lot değeri üretilmedi. `trading_eligibility=ELIGIBLE` yalnız mevcut risk politikasının verilen bağlamda geçmesidir, emir izni değildir. PWA bu kaynağı ve para birimini göstermeden gerçek risk kabulü tamamlanmış sayılamaz.
