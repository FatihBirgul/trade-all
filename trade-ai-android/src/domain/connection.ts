export type ConnectionPhase =
  "unconfigured" | "checking" | "ready" | "offline" | "revoked";
export type ConnectionSnapshot = {
  connectionPhase?: ConnectionPhase;
  connectionError?: string;
  connectionErrorCode?: string | null;
  lastVerifiedAt?: number | null;
};
// A failed fetch cannot distinguish radio, DNS, TLS, private-network or PC failure.
// No network detector is installed: never claim the phone is offline from NETWORK.
export function connectionPresentation(
  c: ConnectionSnapshot,
  now = Date.now(),
) {
  const stale = !!c.lastVerifiedAt && now - c.lastVerifiedAt > 5 * 60000;
  const phase = c.connectionPhase ?? "unconfigured";
  const titles: Record<ConnectionPhase, string> = {
    unconfigured: "Kayıtlı bağlantı yok",
    checking: "Bağlantı doğrulanıyor…",
    ready: stale
      ? "Son bağlantı doğrulaması eski"
      : "Bağlantı son kontrolde doğrulandı",
    offline:
      c.connectionErrorCode === "BACKEND_UNAVAILABLE"
        ? "Gateway yanıtladı · analiz sunucusuna ulaşılamadı"
        : "Kayıtlı PC/Gateway bağlantısı doğrulanamadı",
    revoked: "Mobil oturum reddedildi veya süresi doldu",
  };
  return {
    title: titles[phase],
    stale,
    attention: phase === "offline" || phase === "revoked",
    detail:
      phase === "offline" && c.connectionErrorCode === "NETWORK"
        ? "Gateway’e ulaşılamadı. Telefon ağı, özel ağ/Tailscale, PC veya Gateway kaynaklı olabilir; kesin neden belirlenemedi."
        : c.connectionError ||
          (phase === "ready"
            ? "Bu, son başarılı kontroldür; sürekli erişim veya piyasa verisinin güncelliği garantisi değildir."
            : phase === "unconfigured"
              ? "CANLI için Ayarlar’dan güvenli bağlantı kurun."
              : "CANLI erişimi doğrulama tamamlanana kadar kapalıdır."),
  };
}
