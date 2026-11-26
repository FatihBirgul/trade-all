import type { BotReport, ReportPeriod } from "./types";

// Sunucu kapanan işlemleri UTC'ye göre gün / ISO hafta / ay kovalarına ayırır (repo.pnl_by_period).
// Burada aynı anahtar üretilir ki "bu hafta" ve "bu ay" doğru kovadan okunsun.
export function periodKey(period: ReportPeriod, epochSeconds: number): string {
  const date = new Date(epochSeconds * 1000);
  const year = date.getUTCFullYear();
  const two = (value: number) => String(value).padStart(2, "0");
  if (period === "day") return year + "-" + two(date.getUTCMonth() + 1) + "-" + two(date.getUTCDate());
  if (period === "month") return year + "-" + two(date.getUTCMonth() + 1);
  // ISO hafta: haftanın perşembesi hangi yıldaysa hafta o yıla aittir.
  const thursday = new Date(Date.UTC(year, date.getUTCMonth(), date.getUTCDate()));
  thursday.setUTCDate(thursday.getUTCDate() + 4 - (thursday.getUTCDay() || 7));
  const first = Date.UTC(thursday.getUTCFullYear(), 0, 1);
  const week = Math.ceil(((thursday.getTime() - first) / 86400000 + 1) / 7);
  return thursday.getUTCFullYear() + "-W" + two(week);
}

// Raporun `totals` alanı TÜM zamanların toplamıdır; içinde bulunulan dönemin kâr/zararı `periods` kovasındadır.
// O dönemde kapanan işlem yoksa kova da yoktur: sonuç 0.
export function currentPeriodPnl(report: Pick<BotReport, "period" | "periods">, nowSeconds: number): number {
  const key = periodKey(report.period, nowSeconds);
  return report.periods.all.find((row) => row.period === key)?.pnl ?? 0;
}
