# REAL veriyle varsayımsal risk

REAL_READONLY_DATA modunda eski PWA `balance:10000` alanı yok sayılır. REAL account_info bakiyesi okunmaz. Varsayılan `risk_balance_source=NOT_PROVIDED`, `lot_size=null`, `risk_amount=null`, `trading_eligibility=NOT_EVALUATED`; teknik Entry/SL/TP ancak bütün veri/seans kapıları geçerse gösterilebilir.

Kullanıcı ayrıca pozitif `hypothetical_capital` ve broker hesabıyla exact eşleşen `hypothetical_currency` gönderirse risk hesaplanır; kaynak `HYPOTHETICAL_CAPITAL`, eligibility yine `NOT_EVALUATED`, execution permission daima false olur. USC, USDC ve USD birbirine eşit kabul edilmez. Broker `order_calc_profit` yalnız read-only oracle; ciddi tick-loss uyuşmazlığı veya minimum lot bütçe aşımı bloklanır. PWA'nın mevcut sözleşmesi kırılmadı fakat yeni alanları göstermediğinden varsayımsal lotu uygulanabilir işlem olarak sunmamalıdır.
