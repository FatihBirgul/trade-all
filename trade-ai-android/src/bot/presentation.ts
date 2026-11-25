import { money } from "../domain/safety";
import type { BotStatus } from "./types";

export type Tone = "ok" | "warn" | "bad";

// En ciddi durum önce: kullanıcı tek satırda botun neden işlem açmadığını görmeli.
export function botStateText(
  status: Pick<BotStatus, "halted" | "halt_reason" | "stopped" | "stream_connected" | "dry_run">,
): { label: string; tone: Tone } {
  if (status.halted) return { label: "Durdu: " + (status.halt_reason || "toplam kayıp sınırı"), tone: "bad" };
  if (status.stopped) return { label: "Durduruldu", tone: "warn" };
  if (!status.stream_connected) return { label: "Exness bağlantısı yok", tone: "bad" };
  if (status.dry_run) return { label: "Deneme modu: emir gönderilmiyor", tone: "warn" };
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
