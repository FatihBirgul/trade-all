// Bildirim kuralları (saf). Cihaz tarafı (izin, kanal, token) nativeNotifications.ts içindedir.
import type { BotApi } from "./client";
import type { BotEvent } from "./types";

// Kullanıcının hemen bilmesi gereken olaylar. Tarama/sinyal gibi rutin kayıtlar bildirim üretmez.
export const importantKinds: ReadonlySet<string> = new Set([
  "trade_opened",
  "trade_closed",
  "trade_reopened",
  "sl_breakeven",
  "sl_missing",
  "tp_lost",
  "daily_limit",
  "bot_halted",
  "connection_lost",
  "order_rejected",
  "order_unknown",
  "auth_error",
  "news_unavailable",
  "strategy_paused",
  "startup_failed",
  "capital_base",
  "balance_change",
  "backup_failed",
  "account_blocked",
  "clock_skew",
  "loop_failing",
]);

const LABELS: Record<string, string> = {
  trade_opened: "İşlem açıldı",
  trade_closed: "İşlem kapandı",
  trade_reopened: "Pozisyon yeniden izleniyor",
  sl_breakeven: "SL girişe çekildi",
  sl_missing: "Stop eksik",
  tp_lost: "TP silindi",
  daily_limit: "Günlük limit doldu",
  bot_halted: "Bot durdu",
  bot_stopped: "Bot durduruldu",
  bot_resumed: "Bot devam ediyor",
  bot_started: "Bot başladı",
  capital_base: "Canlı mod başladı",
  mode_changed: "Kip değişti",
  balance_change: "Para yatırma/çekme",
  backup_failed: "Yedek alınamadı",
  account_blocked: "Hesap yeni işleme kapalı",
  clock_skew: "Sunucu saati kaymış",
  loop_failing: "Bot görevi hata veriyor",
  startup_failed: "Bot başlatılamadı",
  connection_lost: "Exness bağlantısı koptu",
  connection_restored: "Exness bağlantısı geri geldi",
  order_rejected: "Emir reddedildi",
  order_unknown: "Emir sonucu bilinmiyor",
  auth_error: "API erişimi reddedildi",
  auth_restored: "API erişimi düzeldi",
  news_unavailable: "Haber takvimi alınamıyor",
  strategy_paused: "Strateji duraklatıldı",
  strategy_mode: "Strateji kipi değişti",
  settings_changed: "Ayar değişti",
  device_paired: "Cihaz eşleştirildi",
  close_all: "Hepsini kapat istendi",
  rate_limited: "İstek sınırına takıldı",
  reconcile_error: "Hesap eşitleme hatası",
  scan: "Tarama",
  scan_skipped: "Tarama atlandı",
  signal: "Sinyal",
  signal_observed: "Sinyal (gölge)",
  signal_invalid: "Geçersiz sinyal",
};
export const kindLabel = (kind: string): string => LABELS[kind] ?? kind;

// Bildirim sekmesinin "Önemli" görünümü: önemli türler ve her uyarı/hata.
export const isImportant = (event: Pick<BotEvent, "kind" | "level">): boolean =>
  importantKinds.has(event.kind) || event.level === "error" || event.level === "warning";

export type Schedule = (title: string, body: string) => void | Promise<void>;

function safely(schedule: Schedule, title: string, body: string) {
  try {
    void Promise.resolve(schedule(title, body)).catch(() => {});
  } catch {
    // Bildirim gösterilemese de olay akışı çalışmaya devam eder.
  }
}

export const FRESH_SECONDS = 600; // bundan eski olay "yeni" gibi tek tek bildirilmez
export const MAX_SINGLE = 3; // bir seferde en çok bu kadar ayrı bildirim; gerisi tek özet

// Uygulama açıkken gelen önemli olaylar için yerel bildirim. Görülen en büyük kimliği döndürür;
// aynı olay ikinci kez bildirilmez. Uygulama saatlerce arka planda kaldıysa birikmiş olaylar tek tek
// "az önce olmuş" gibi yağmaz: yalnızca son 10 dakikanın en yeni üçü ayrı, kalanı tek özet bildirilir.
export function notifyNewEvents(
  events: readonly BotEvent[],
  lastSeenId: number,
  schedule: Schedule,
  nowSeconds?: number,
): number {
  let seen = lastSeenId;
  const important: BotEvent[] = [];
  for (const event of [...events].sort((a, b) => a.id - b.id)) {
    if (event.id <= seen) continue;
    seen = event.id;
    if (importantKinds.has(event.kind)) important.push(event);
  }
  const fresh =
    nowSeconds === undefined ? important : important.filter((event) => nowSeconds - event.at <= FRESH_SECONDS);
  const single = fresh.slice(-MAX_SINGLE);
  for (const event of single) safely(schedule, kindLabel(event.kind), event.message);
  const rest = important.length - single.length;
  if (rest > 0)
    safely(
      schedule,
      rest + " önemli olay daha",
      "Uygulama kapalıyken ya da kısa sürede birden çok olay oldu. Bildirimler sekmesine bakın.",
    );
  return seen;
}

// Kalp atışı kaybı: bayatlama başladığında bir kez bildirir; düzelip yeniden bozulursa yine bir kez.
export function heartbeatNotifier(schedule: Schedule): (stale: boolean) => void {
  let alerted = false;
  return (stale) => {
    if (!stale) {
      alerted = false;
      return;
    }
    if (alerted) return;
    alerted = true;
    safely(
      schedule,
      "Bottan 5 dakikadır haber yok",
      "Sunucuyu kontrol edin. Açık pozisyonların SL emirleri Exness tarafında durur.",
    );
  };
}

// Uzak (uygulama kapalıyken) bildirim kaydı. Token alınamıyorsa (FCM yapılandırılmamış) sessizce false.
export async function registerPush(
  api: Pick<BotApi, "registerDevice">,
  getToken: () => Promise<string | null>,
): Promise<boolean> {
  try {
    const token = await getToken();
    if (!token) return false;
    await api.registerDevice(token);
    return true;
  } catch {
    return false;
  }
}
