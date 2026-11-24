# Official macro source research (2026-11-06)

- BLS calendar/import instructions: https://www.bls.gov/help/hlpiCAL.htm
- BLS ICS: https://www.bls.gov/schedule/news_release/bls.ics
- BLS public-domain text policy, with third-party image exceptions:
  https://www.bls.gov/bls/linksite.htm and https://www.bls.gov/opub/copyright-information.htm
- Federal Reserve official RSS directory: https://www.federalreserve.gov/feeds/feeds.htm
  Monetary policy RSS: https://www.federalreserve.gov/feeds/press_monetary.xml
- ECB official meeting schedule: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
- BoE official MPC dates: https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates
- BoJ official meeting schedule: https://www.boj.or.jp/en/mopo/mpmsche_minu/

Search/read evidence supports these source locations; it does not establish an
all-events calendar contract. Only BLS ICS has a new bounded retrieval/parser adapter.
Actual observed probe:313 events,21 future events,0 rejected records, last release
2026-12-30; exact retrieved UTC time/hash is V7_BLS_PROBE.json. No full feed republished.
BLS event records omit DTSTAMP and use a US-Eastern VTIMEZONE name; source publication
is NULL and first knowledge is retrieval, explicitly labelled. No actual/forecast
values are invented. Feed success does not verify coverage. Fed RSS can use the
retained Day Trader parser after explicit caller ingestion; ECB/BoE/BoJ complete
provider adapters and reuse/coverage/freshness review remain PARTIAL. BEA GDP and
other official agencies need separate adapter/terms review. Economic events are
risk context and cannot authorize a BUY/SELL forecast. No scheduled downloader or
external alert delivery was activated. Network failures return DATA_UNAVAILABLE.
