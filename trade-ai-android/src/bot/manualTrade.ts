import * as SecureStore from "expo-secure-store";
import type { PreviewRequest, TradePreview, TradeRequest, TradeResult } from "./types";

// Sonucu bilinmeyen elle emir. Ekran kapanıp açılsa da (ya da uygulama öldürülse de) hatırlanır: kullanıcı
// sonucu öğrenmeden ikinci bir emir gönderemez.
export type PendingTrade = { id: string; trade: TradeRequest; at: number };

const KEY = "tradebot_pending_manual_trade";
export const PREVIEW_MAX_AGE_MS = 60_000;
export const RISK_PCT_MIN = 0.05; // sunucudaki ManualPreview.risk_pct sınırlarıyla aynı
export const RISK_PCT_MAX = 2;

export async function loadPending(): Promise<PendingTrade | null> {
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as PendingTrade;
    if (typeof value?.id !== "string" || typeof value?.trade?.symbol !== "string" || typeof value?.at !== "number") return null;
    return value;
  } catch {
    return null;
  }
}
export async function savePending(pending: PendingTrade): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify(pending));
}
export async function clearPending(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(KEY);
  } catch {
    // Silinemezse bir sonraki açılışta yeniden sorulur; sunucu aynı kimlikle ikinci emir açmaz.
  }
}

// Önizleme yalnızca kendi isteği için geçerlidir: başka sembol/yön/mesafe için gelen yanıt kullanılmaz.
export function sameRequest(a: PreviewRequest, b: PreviewRequest): boolean {
  return (
    a.symbol === b.symbol &&
    a.side === b.side &&
    a.sl_distance === b.sl_distance &&
    (a.tp_distance ?? null) === (b.tp_distance ?? null) &&
    (a.lots ?? null) === (b.lots ?? null) &&
    (a.risk_pct ?? null) === (b.risk_pct ?? null)
  );
}
export function previewMatches(preview: TradePreview, trade: TradeRequest): boolean {
  return preview.symbol === trade.symbol && preview.side === trade.side;
}

// Sunucu 200 dönse de emir reddedilmiş ya da sonucu bilinmiyor olabilir.
export function resultNotice(result: Pick<TradeResult, "state" | "lots" | "duplicate">, lotText: string): { text: string; bad: boolean } {
  const state = (result.state ?? "").toUpperCase();
  if (state === "REJECTED") return { text: "Emir REDDEDİLDİ; pozisyon açılmadı. Ayrıntı Bildirimler sekmesinde.", bad: true };
  if (state === "UNKNOWN" || state === "PENDING" || state === "")
    return { text: "Emir sunucuya ulaştı ama sonucu henüz bilinmiyor. Yeni emir göndermeden önce Pozisyonlar sekmesine bakın.", bad: true };
  return {
    text: (result.duplicate ? "Emir daha önce alınmış: " : "Emir gönderildi: ") + lotText + " lot. Pozisyonlar sekmesinden izleyin.",
    bad: false,
  };
}
