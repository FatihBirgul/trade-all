import { activationObservation } from "./scannerReadiness";
export type HealthStatus =
  | "ONLINE"
  | "OFFLINE"
  | "BACKEND_UNAVAILABLE"
  | "GATEWAY_UNAVAILABLE"
  | "PROVIDER_UNAVAILABLE"
  | "WORKER_INACTIVE"
  | "UNAUTHORIZED"
  | "DEGRADED"
  | "RECOVERING"
  | "UNKNOWN";
export type HealthInput = {
  gatewayVerified: boolean;
  mode: string;
  phase?: string;
  errorCode?: string | null;
  errorStatus?: number;
  recovering?: boolean;
  deviceOnline?: boolean;
  account: string;
  accounts?: readonly string[];
  scopes?: readonly string[];
  runtime?: Record<string, unknown>;
  observedAt?: number | null;
  stale?: boolean;
  scanIntervalMs?: number;
  now: number;
};
export function validTime(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= 0 &&
    value <= 253402300799999
  );
}
export function healthStatus(i: HealthInput): {
  status: HealthStatus;
  title: string;
  detail: string;
} {
  const result = (status: HealthStatus, title: string, detail: string) => ({
    status,
    title,
    detail,
  });
  if (i.deviceOnline === false)
    return result(
      "OFFLINE",
      "Telefon ağı çevrimdışı olarak bildirildi",
      "Yalnız açık ağ-adapter kanıtı; PC veya Backend durumu bundan çıkarılamaz.",
    );
  if (
    i.errorStatus === 401 ||
    i.errorStatus === 403 ||
    ["SCOPE_DENIED", "UNAUTHORIZED"].includes(i.errorCode ?? "") ||
    i.phase === "revoked"
  )
    return result(
      "UNAUTHORIZED",
      "Oturum / hesap yetkisi doğrulanamadı",
      "403 oturumu silmez. Gerekli hesap ve okuma yetkisini kontrol edin.",
    );
  if (i.recovering || i.phase === "checking")
    return result(
      "RECOVERING",
      "Bağlantı yeniden doğrulanıyor",
      "Doğrulama tamamlanana kadar eski veri güncel kabul edilmez. Worker başlatılmaz.",
    );
  if (i.errorCode === "GATEWAY_UNAVAILABLE")
    return result(
      "GATEWAY_UNAVAILABLE",
      "Gateway erişilemiyor olarak bildirildi",
      "Bu sınıflandırma açık tanı koduna dayanır; PC'nin kapalı olduğunu kanıtlamaz.",
    );
  if (
    ["BACKEND_UNAVAILABLE", "BACKEND_AUTH_FAILED", "UPSTREAM_TIMEOUT"].includes(
      i.errorCode ?? "",
    )
  )
    return result(
      "BACKEND_UNAVAILABLE",
      "Gateway yanıtladı · Backend doğrulanamadı",
      "Bağlantı, Backend yetkisi veya süre aşımı sorunu olabilir; worker durumu bilinmiyor.",
    );
  if (
    ["NETWORK", "NETWORK_ERROR"].includes(i.errorCode ?? "") ||
    i.phase === "offline"
  )
    return result(
      "UNKNOWN",
      "Bağlantı kaybının nedeni bilinmiyor",
      "Telefon, DNS/TLS, Gateway, özel ağ veya PC kaynaklı olabilir. İnternet ya da PC kapalı varsayılmaz.",
    );
  if (i.mode !== "live" || !i.gatewayVerified)
    return result(
      "UNKNOWN",
      "Canlı sunucu sağlığı doğrulanmadı",
      "Demo ve kayıtlı oturum, çalışan Backend veya worker kanıtı değildir.",
    );
  if (!i.accounts?.includes(i.account) || !i.scopes?.includes("read"))
    return result(
      "UNAUTHORIZED",
      "Bu hesap okunamıyor",
      "Başka hesabın kayıtları gösterilmez.",
    );
  if (
    i.errorCode ||
    i.stale ||
    !validTime(i.observedAt) ||
    i.now < i.observedAt ||
    i.now - i.observedAt > 120000
  )
    return result(
      "DEGRADED",
      "Sağlık gözlemi eksik veya eski",
      "Son başarılı bilgi korunabilir; güncel hizmet durumu gibi gösterilmez. Yenileyin.",
    );
  const a = activationObservation(i.runtime);
  if (!a)
    return result(
      "DEGRADED",
      "Worker gözlemi doğrulanamadı",
      "Eski sürüm veya geçersiz yanıt olabilir. Çalışıyor varsayılmaz.",
    );
  if (!a.runtime_available || i.runtime?.worker_stopping === true)
    return result(
      "WORKER_INACTIVE",
      "Aktif worker doğrulanmadı",
      "Tarama isteği kayıtlı olsa da host runtime ayrı ve açık operatör seçimi gerektirir.",
    );
  const interval =
    Number.isSafeInteger(i.scanIntervalMs) &&
    i.scanIntervalMs! >= 60000 &&
    i.scanIntervalMs! <= 3600000
      ? i.scanIntervalMs!
      : 300000;
  const sourceAt =
    i.runtime?.provider_status === "reachable"
      ? i.runtime.last_success_ms
      : i.runtime?.last_attempt_ms;
  if (
    !validTime(sourceAt) ||
    i.now < sourceAt ||
    i.now - sourceAt > interval + 30000
  )
    return result(
      "DEGRADED",
      "Piyasa kontrolü eski veya bilinmiyor",
      "Taze Backend yanıtı eski sağlayıcı kaydını yenilemez. Son tarama zamanı ayrı değerlendirilir.",
    );
  if (
    ["unavailable", "circuit_open"].includes(String(i.runtime?.provider_status))
  )
    return result(
      "PROVIDER_UNAVAILABLE",
      "Son sağlayıcı kaydı: kullanılamıyor",
      "Backend erişimi, güncel fiyat veya fırsat üretilebildiği anlamına gelmez.",
    );
  if (i.runtime?.provider_status !== "reachable")
    return result(
      "DEGRADED",
      "Piyasa kaynağı henüz tam doğrulanmadı",
      "Worker heartbeat'i mevcut; kaynak denenmemiş, kısmen kullanılabilir veya bilinmiyor.",
    );
  return result(
    "ONLINE",
    "Sunucu / worker gözlemi güncel",
    "Yakın zamandaki doğrulanmış gözlem; sürekli erişim, etkin hesap veya kazanç garantisi değildir.",
  );
}
export type HealthMemory = {
  scope: string;
  failedSince: number | null;
  lastRecoveredAt: number | null;
};
export function observeHealth(
  old: HealthMemory,
  scope: string,
  at: number,
  failed: boolean,
  succeeded: boolean,
): HealthMemory {
  const current =
    old.scope === scope
      ? old
      : { scope, failedSince: null, lastRecoveredAt: null };
  if (!validTime(at)) return current;
  if (failed)
    return current.failedSince === null
      ? { ...current, failedSince: at }
      : current;
  if (succeeded && current.failedSince !== null)
    return { ...current, failedSince: null, lastRecoveredAt: at };
  return current;
}
export function observedDuration(since: number | null, now: number): string {
  if (!validTime(since) || !validTime(now) || now < since) return "Bilinmiyor";
  const seconds = Math.floor((now - since) / 1000);
  return seconds < 60 ? seconds + " sn" : Math.floor(seconds / 60) + " dk";
}
