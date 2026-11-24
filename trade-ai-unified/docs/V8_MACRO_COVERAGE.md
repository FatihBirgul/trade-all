# V8 official macro coverage and usage

New official_calendar adapters use fixed official URLs, no arbitrary network URL,
8-second timeout,512KB bound, no redirects/retries/fixture fallback. Fetch is explicit;
startup/analysis never starts hidden downloads. usage_reviewed defaults false.
Source payload/hash/retrieval/coverage and parse failures are explicit. API provider
must be configured separately; successful development probes are not an always-on
verified calendar service.

| Source | Observed integration | Time/coverage limitation |
|---|---|---|
| BLS | Existing bounded ICS retained; CPI/NFP | Per-event source publication unavailable |
| Fed | HTML meeting dates54 in probe; RSS announcement parser | Cross-month formats partly unsupported; DATE_ONLY |
| ECB | HTML monetary meeting dates34 in probe | DATE_ONLY; non-monetary excluded |
| BEA | Official ICS169 in probe, GDP classification | Explicit UTC release; calendar record stamp is NOT publication |
| BoE | Date-table parser fixture-tested; actual request HTTP403 | Live unavailable, no bypass/fallback |
| BoJ | Date-table parser fixture-tested | Usage review/possible commercial permission required |

DateEvent release_utc/published_utc are NULL when source supplies only dates. Known
at/retrieval are separate, timezone explicit. Optional macro filter conservatively
vetoes the declared local meeting date/range without fabricating an exact release
clock. Unknown coverage never means all-event protection. Precise actual values
cannot be known before release; revisions are selected only as-of-known. Equal
source revision with conflicting contents is refused even if retrieved later.

ICS DTSTAMP is a record timestamp, not proven source publication. V8 exposes it as
source_record_timestamp; published_utc stays NULL. Retained published_at field is
explicitly FIRST_OBSERVED_RETRIEVAL for compatibility, not a source publication
assertion. Freshness/known_at are distinct. No actual/forecast values are invented.

Observed URLs/counts/hash/timestamps: V8_OFFICIAL_SOURCE_PROBE.json. Official terms:
- Fed calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
  disclaimer: https://www.federalreserve.gov/disclaimer.htm
- ECB: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
  reuse requires accuracy/source citation: https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html
- BEA ICS: https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics
  public-domain exceptions: https://www.bea.gov/help/faq/147
- BLS: https://www.bls.gov/help/hlpiCAL.htm and https://www.bls.gov/bls/linksite.htm
- BoE: https://www.bankofengland.co.uk/legal (personal/internal non-commercial terms,
  permissions may be required); schedule direct request403.
- BoJ: https://www.boj.or.jp/en/about/copyright.htm (credit source; commercial copying
  can require permission). No permission request/message was sent.

Only factual normalized schedule metadata/counts were saved; no full feed/page
republished. These are reviewed source notes, not legal certification. Tests cover
source-specific fixtures, malformed/timezone/date/schema, payload/encoding/network
failure, unknown source, missing publication and as-of date-only risk context.
