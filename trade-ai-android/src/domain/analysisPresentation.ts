import type { Analysis } from "./safety";
export const notEvaluated =
  "Veri bulunmadığı veya doğrulanamadığı için değerlendirilemedi.";
// Historical assessment, independent of current expiry. This never changes safeDecision.
export function hasMarketEvaluation(a: Analysis): boolean {
  return (
    a.data_mode === "live" &&
    a.quality.ok === true &&
    typeof a.price === "string" &&
    /^\d+(?:\.\d+)?$/.test(a.price) &&
    Number.isFinite(Number(a.price)) &&
    Number(a.price) > 0 &&
    Number.isSafeInteger(a.price_time_ms) &&
    !!a.price_time_ms &&
    a.price_time_ms > 0 &&
    a.price_time_ms <= a.created_at_ms
  );
}
export function regimeText(a: Analysis): string {
  if (!hasMarketEvaluation(a)) return notEvaluated;
  return (
    (
      {
        range: "Yatay piyasa",
        trend: "Trend piyasası",
        transition: "Geçiş piyasası",
        volatile: "Yüksek oynaklık",
      } as Record<string, string>
    )[String(a.regime.regime)] ?? "Piyasa rejimi açıklaması sağlanmadı."
  );
}
export function validityText(a: Analysis): string {
  if (!hasMarketEvaluation(a))
    return "Uygulanabilir işlem senaryosu yok · piyasa verisi doğrulanmadı.";
  if (a.direction === "WAIT")
    return "Bekle kararı · işlem senaryosu oluşturulmadı.";
  return "Kaydın süre ve güvenlik koşulları ayrıca denetlenir.";
}
