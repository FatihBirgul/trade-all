const supported = new Set(["BTCUSDT", "ETHUSDT", "SOLUSDT"]);
export type CatalogueRow = {
  symbol: string;
  market: string;
  source: string;
  venue: string;
  selectable: boolean;
  sourceStatus: string;
};
export function catalogueRows(payload: unknown): CatalogueRow[] {
  if (
    !payload ||
    typeof payload !== "object" ||
    !Array.isArray((payload as { items?: unknown }).items)
  )
    throw Error("Katalog doğrulanamadı.");
  const p = payload as { data_mode?: unknown; items: unknown[] };
  if (p.data_mode !== "live" || p.items.length > 200)
    throw Error("Canlı katalog kimliği veya sınırı doğrulanamadı.");
  const result: CatalogueRow[] = [];
  const seen = new Map<string, string>();
  for (const raw of p.items) {
    if (!raw || typeof raw !== "object") throw Error("Geçersiz katalog kaydı.");
    const r = raw as Record<string, unknown>;
    if (
      typeof r.symbol !== "string" ||
      !/^[A-Z0-9]{3,20}$/.test(r.symbol) ||
      typeof r.market !== "string"
    )
      throw Error("Enstrüman kimliği geçersiz.");
    const identity = JSON.stringify([
      r.market,
      r.venue ?? null,
      r.provider ?? null,
      r.contract_type ?? null,
    ]);
    if (seen.has(r.symbol)) {
      if (seen.get(r.symbol) !== identity)
        throw Error("Katalogda çelişkili enstrüman kimliği.");
      continue;
    }
    seen.set(r.symbol, identity);
    result.push({
      symbol: r.symbol,
      market: r.market,
      source:
        typeof r.provider === "string"
          ? r.provider
          : "Doğrulanmış sağlayıcı yok",
      venue: typeof r.venue === "string" ? r.venue : "Belirtilmemiş",
      selectable:
        supported.has(r.symbol) &&
        r.market === "crypto_spot" &&
        r.contract_type === "spot" &&
        r.availability === "configured" &&
        typeof r.provider === "string" &&
        typeof r.venue === "string" &&
        r.quote_currency === "USDT",
      sourceStatus:
        typeof r.provider_status === "string"
          ? r.provider_status
          : "unavailable",
    });
  }
  return result;
}
export function findMarkets(
  rows: CatalogueRow[],
  query: string,
  filter: string,
  favorites: readonly string[],
) {
  const needle = query.toUpperCase().replace(/[^A-Z0-9]/g, "");
  return rows.filter(
    (r) =>
      (!needle || r.symbol.includes(needle)) &&
      (filter !== "Favoriler" || favorites.includes(r.symbol)) &&
      (filter !== "Spot" || r.market === "crypto_spot") &&
      (filter !== "Kullanılamayan" || !r.selectable),
  );
}
export function marketType(market: string) {
  return (
    (
      {
        crypto_spot: "Kripto spot",
        forex_spot: "Forex · desteklenmiyor",
        gold_spot: "Altın · desteklenmiyor",
      } as Record<string, string>
    )[market] ?? "Piyasa türü doğrulanmadı"
  );
}
