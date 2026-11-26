import { money } from "./base";
import type { BotStatus } from "./types";

export type Tone = "ok" | "warn" | "bad";

// En ciddi durum önce: kullanıcı tek satırda botun neden işlem açmadığını görmeli.
export function botStateText(
  status: Pick<BotStatus, "halted" | "halt_reason" | "stopped" | "stream_connected" | "dry_run">,
): { label: string; tone: Tone } {
  if (status.halted) return { label: "Durdu: " + (status.halt_reason || "toplam kayıp sınırı"), tone: "bad" };
  if (status.stopped) return { label: "Durduruldu", tone: "warn" };
  if (!status.stream_connected) return { label: "Exness bağlantısı yok", tone: "bad" };
  if (status.dry_run) return { label: "Deneme modu: bot emir göndermiyor", tone: "warn" };
  return { label: "Çalışıyor", tone: "ok" };
}

export function amountText(value: number | null | undefined, currency?: string | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return money(value.toFixed(2)) + (currency ? " " + currency : "");
}

// Kâr/zarar: işaret her zaman yazılır ki renk görülmese de yön anlaşılsın.
export function pnlText(value: number | null | undefined, currency?: string | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const rounded = Math.round(value * 100) / 100;
  const body = money(Math.abs(rounded).toFixed(2)) + (currency ? " " + currency : "");
  return rounded > 0 ? "+" + body : rounded < 0 ? "−" + body : body;
}

export function pnlTone(value: number | null | undefined): Tone | null {
  if (value == null || !Number.isFinite(value) || Math.round(value * 100) === 0) return null;
  return value > 0 ? "ok" : "bad";
}

export function agoText(epochSeconds: number | null | undefined, nowSeconds: number): string {
  if (epochSeconds == null) return "henüz yok";
  const seconds = Math.max(0, Math.floor(nowSeconds - epochSeconds));
  if (seconds < 60) return "az önce";
  if (seconds < 3600) return Math.floor(seconds / 60) + " dk önce";
  if (seconds < 86400) return Math.floor(seconds / 3600) + " sa önce";
  return Math.floor(seconds / 86400) + " gün önce";
}

export function priceText(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  // Fiyatlar sunucudan geldiği hassasiyetle gösterilir; gereksiz sıfır eklenmez.
  return String(Number(value.toFixed(6))).replace(".", ",");
}

const two = (value: number) => String(value).padStart(2, "0");
// "25.11 14:32" — telefonun yerel saatiyle.
export function timeText(epochSeconds: number): string {
  const date = new Date(epochSeconds * 1000);
  return (
    two(date.getDate()) + "." + two(date.getMonth() + 1) + " " + two(date.getHours()) + ":" + two(date.getMinutes())
  );
}

// "+1,25R" / "−0,45R". Sıfıra yuvarlanan değer işaretsiz yazılır.
export function rText(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "";
  const rounded = Math.round(value * 100) / 100;
  const body = priceText(Math.abs(rounded)) + "R";
  return rounded > 0 ? "+" + body : rounded < 0 ? "−" + body : body;
}

export function clockText(epochMs: number): string {
  const date = new Date(epochMs);
  return two(date.getHours()) + ":" + two(date.getMinutes()) + ":" + two(date.getSeconds());
}

// Deneme modu yalnızca botun kendi emirlerini durdurur; kullanıcının verdiği emirler gerçektir.
export const REAL_ACTION_NOTE = "Deneme modunda bile bu işlem GERÇEK hesapta yapılır.";

// Botun bir sinyali neden açmadığını anlatan kısa Türkçe karşılıklar (sunucu İngilizce kısa neden döndürür).
const VETO: [RegExp, string][] = [
  [/no_eligible_strategy/, "uygun kurulum yok"],
  [/higher bias|lower trigger/, "üst zaman dilimi uyumsuz"],
  [/missing candle/, "eksik mum"],
  [/stale tick|stale/, "fiyat bayat"],
  [/max_spread missing/, "spread ölçümü hazır değil"],
  [/spread exceeds/, "spread yüksek"],
  [/opposing strategy/, "karşıt sinyal"],
  [/high volatility/, "oynaklık yüksek"],
  [/provider unavailable/, "fiyat akışı yok"],
  [/broker market|market closed/, "piyasa kapalı"],
  [/reward\/risk/, "kâr/zarar oranı yetersiz"],
];
export const vetoText = (reason: string): string => VETO.find(([pattern]) => pattern.test(reason))?.[1] ?? reason;

// Cent hesaplar (Exness): tutarlar ana para biriminin yüzde biri cinsindendir (100 USC = 1 USD).
export const CENT_CURRENCY: Record<string, string> = { USC: "USD", EUC: "EUR", GBC: "GBP" };
export const isCent = (currency: string | null | undefined): boolean => !!currency && currency in CENT_CURRENCY;
// Cent hesapta tutarın ana para birimindeki karşılığı: "≈ 30,00 USD". Cent hesap değilse boş metin.
export function majorText(value: number | null | undefined, currency: string | null | undefined, signed = false): string {
  if (value == null || !Number.isFinite(value) || !currency || !isCent(currency)) return "";
  const major = CENT_CURRENCY[currency];
  return "≈ " + (signed ? pnlText(value / 100, major) : amountText(value / 100, major));
}
export const centNote = (currency: string | null | undefined): string =>
  currency && isCent(currency) ? "Tutarlar " + currency + " (cent) cinsindendir: 100 " + currency + " = 1 " + CENT_CURRENCY[currency] + "." : "";
