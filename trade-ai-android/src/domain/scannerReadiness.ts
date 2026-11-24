import type { ConnectionPhase } from "./connection";
export const activationReason: Record<string, string> = {
  runtime_not_running:
    "Sunucu worker süreci açık değil veya güncel heartbeat doğrulanamadı. Yetkili operatörün runtime seçimi gerekir.",
  worker_stopping: "Worker durduruluyor; tamamlanmasını bekleyin.",
  runtime_mode_required: "Önce çalışma modu seçip ayarları pasif kaydedin.",
  runtime_off: "Çalışma modu kapalı.",
  profile_required: "Hesabınıza ait sabit bir strateji profil revizyonu seçin.",
  selected_profile_requires_favorites_mode:
    "Seçili profil modu yalnız favorileri tarar.",
  discovery_scope_required: "Desteklenen spot modu için keşif kapsamı gerekir.",
  empty_scope: "En az bir favori parite veya desteklenen keşif kapsamı seçin.",
};
export type ActivationObservation = {
  state: "blocked" | "active" | "ready_to_activate";
  reasons: string[];
  runtime_available: boolean;
  account_enabled: boolean;
  starts_process: false;
};
export function activationObservation(
  runtime?: Record<string, unknown>,
): ActivationObservation | null {
  const value = runtime?.activation;
  if (!value || typeof value !== "object") return null;
  const a = value as ActivationObservation;
  if (
    !["blocked", "active", "ready_to_activate"].includes(a.state) ||
    !Array.isArray(a.reasons) ||
    a.reasons.length > 16 ||
    a.reasons.some((r) => typeof r !== "string" || !/^[a-z_]{1,64}$/.test(r)) ||
    typeof a.runtime_available !== "boolean" ||
    typeof a.account_enabled !== "boolean" ||
    a.starts_process !== false
  )
    return null;
  if (
    a.state !== "blocked" &&
    (!a.runtime_available ||
      a.reasons.length ||
      a.account_enabled !== (a.state === "active"))
  )
    return null;
  return a;
}
export function scannerReadiness(input: {
  mode: string;
  gatewayVerified: boolean;
  phase?: ConnectionPhase;
  errorCode?: string | null;
  errorStatus?: number;
  accounts?: readonly string[];
  account: string;
  scopes?: readonly string[];
  capabilities?: readonly string[];
  runtime?: Record<string, unknown>;
}) {
  const { errorCode: code, scopes = [], runtime } = input;
  const state = (
    status: "offline" | "partial" | "unauthorized" | "ready",
    title: string,
    detail: string,
  ) => ({ status, title, detail });
  if (
    code === "UNAUTHORIZED" ||
    code === "SCOPE_DENIED" ||
    input.errorStatus === 403 ||
    input.phase === "revoked"
  )
    return state(
      "unauthorized",
      "Bağlı ama yetkisiz",
      "Oturum veya hesap yetkisi doğrulanamadı. 403 oturumu silmez; gerekli yetkiyi Ayarlar üzerinden kontrol edin.",
    );
  if (
    code === "BACKEND_UNAVAILABLE" ||
    code === "BACKEND_AUTH_FAILED" ||
    code === "UPSTREAM_TIMEOUT"
  )
    return state(
      "partial",
      "Kısmi bağlı · Backend doğrulanamadı",
      "Gateway yanıt verdi; Backend erişimi veya yapılandırması doğrulanamadı. Worker durumu bilinmiyor.",
    );
  if (
    code === "NETWORK" ||
    code === "NETWORK_ERROR" ||
    input.phase === "offline"
  )
    return state(
      "offline",
      "Çevrimdışı · sunucu bağlantısı doğrulanamadı",
      "Telefon interneti, Gateway, özel ağ veya PC kaynaklı olabilir; kesin neden belirlenmedi. Worker'ın durduğu varsayılmaz.",
    );
  if (input.mode !== "live" || !input.gatewayVerified)
    return state(
      "offline",
      "Canlı bağlantı doğrulanmadı",
      "Demo sonuçlarıyla worker hazır gösterilmez. Bağlantıyı açıkça yeniden doğrulayın.",
    );
  if (
    !input.accounts?.includes(input.account) ||
    !scopes.includes("read") ||
    !scopes.includes("discovery:write")
  )
    return state(
      "unauthorized",
      "Bağlı ama yetkisiz · salt okunur",
      "Bu hesapta tarama yazma/aktivasyon yetkisi yok. Paper veya eski scanner yetkisi bunu açmaz.",
    );
  if (
    !input.capabilities?.includes("scanner-activation-v1") ||
    code === "BACKEND_UPDATE_REQUIRED"
  )
    return state(
      "partial",
      "Kısmi bağlı · güncelleme gerekli",
      "Profil/aktivasyon kontrolü için uyumlu Backend ve Gateway gerekir.",
    );
  if (code)
    return state(
      "partial",
      "Kısmi bağlı · durum doğrulanamadı",
      "Sunucu yanıtı veya kaynak geçerli değil. Sonuçları güncel kabul etmeden yenileyin.",
    );
  const activation = activationObservation(runtime);
  if (!activation)
    return state(
      "partial",
      "Kısmi bağlı · worker durumu bilinmiyor",
      "Sunucu durumu henüz doğrulanmadı veya Backend güncellemesi gerekiyor.",
    );
  if (activation.state === "blocked")
    return state(
      "partial",
      "Kısmi bağlı · etkinleştirme bekliyor",
      Array.isArray(activation.reasons)
        ? activation.reasons
            .map((x) => activationReason[String(x)] ?? "Koşul doğrulanamadı.")
            .join(" ")
        : "Aktivasyon koşulları doğrulanamadı.",
    );
  if (
    ["unavailable", "circuit_open", "partial"].includes(
      String(runtime?.provider_status),
    )
  )
    return state(
      "partial",
      "Kısmi bağlı · piyasa kaynağı hazır değil",
      "Worker heartbeat'i mevcut; sağlayıcı kesintisi/kalite sorunu ayrı değerlendirilir. Gerçek provider doğrulanmış sayılmaz.",
    );
  return state(
    "ready",
    activation.state === "active"
      ? "Hazır · hesap etkin"
      : "Hazır · açık etkinleştirme bekleniyor",
    "Yakın zamandaki lease/heartbeat gözlemi; sürekli çalışma, gerçek piyasa veya push teslimi garantisi değildir.",
  );
}
