export function reasonText(reason: string): string {
  if (reason.startsWith("profile_filter:"))
    return "Profil filtresi: " + reasonText(reason.slice(15));
  const known: Record<string, string> = {
    strategy_not_selected: "Seçilen profil bu stratejiyi içermiyor.",
    regime_not_selected:
      "Piyasa rejimi profilin izin verdiği koşullarda değil.",
    existing_risk_gate:
      "Mevcut risk kapısı uygun değil; profil bunu değiştiremez.",
    analysis_wait_or_bad_quality:
      "Analiz BEKLE durumunda veya veri kalitesi yetersiz.",
    required_indicator_unavailable:
      "Profilin gerekli indikatörlerinden biri hesaplanamadı.",
    distinct_confirmations_missing:
      "Yeterli bağımsız teyit yok; aynı veriler tekrar sayılmadı.",
    profile_timeframes_missing:
      "Profilin zaman dilimi rolleri bu kayıtta bulunmuyor.",
    strategy_version_missing_or_mismatch:
      "Kaydın strateji sürümü profil ile eşleşmiyor.",
    existing_analysis_and_profile_filter_pass:
      "Mevcut analiz profil koşullarını da sağlıyor; bu bağımsız işlem izni değildir.",
    SCANNER_WATCH_CHANGED:
      "İzleme ayarları analiz sırasında değişti; eski ayarlarla sonuç kaydedilmedi.",
    stale_analysis:
      "Bu analizin güncellik süresi doldu; yeni değerlendirme bekleniyor.",
    TRACKING_WORKER_ERROR:
      "Takip işçisi kontrolü tamamlayamadı. PC’deki servis durumunu kontrol edin.",
    regime_not_eligible:
      "Piyasanın mevcut yapısı bu stratejinin koşullarını sağlamıyor.",
    entry_confirmation_missing: "Giriş koşulları henüz teyit edilmedi.",
    continuation_confirmed_requires_legacy_confluence:
      "Trend devamı teyitli; diğer analiz koşullarının da uyumlu olması gerekiyor.",
    conditional_setup:
      "Güncel veriler koşullu bir görünümü destekliyor. Bu bir emir veya başarı garantisi değildir.",
    eligible_priority:
      "Router, koşulları sağlayan stratejiler arasından öncelikli olanı seçti.",
    no_eligible_strategy: "Mevcut koşullarda uygun strateji bulunamadı.",
    local_demo_no_market_data: "Yerel DEMO: piyasa verisi yok.",
    provider_unavailable: "Piyasa veri sağlayıcısına ulaşılamıyor.",
    strategy_confirmation_missing: "Strateji teyidi eksik.",
    strategy_reward_risk_gate: "Getiri/risk koşulu sağlanmadı.",
    opposing_strategy_conflict: "Stratejiler arasında çelişki var.",
    mtf_strategy_conflict: "Zaman dilimleri arasında çelişki var.",
    strategy_direction_conflict: "Strateji yönleri çelişiyor.",
  };
  return known[reason] ?? "Neden kodu: " + reason;
}
export function directionText(direction: string): string {
  return direction === "bullish"
    ? "Yükseliş"
    : direction === "bearish"
      ? "Düşüş"
      : direction === "WAIT" || direction === "wait"
        ? "Bekle"
        : direction === "neutral"
          ? "Nötr"
          : "Yön değerlendirmesi yok";
}
export function technicalStatusText(status: unknown): string {
  if (status === "available") return "Hesaplandı";
  if (status === "unavailable" || status === "not_available")
    return "Kullanılamıyor";
  if (status === "insufficient_data") return "Yetersiz veri";
  if (status === "not_configured") return "Yapılandırılmadı";
  const states: Record<string, string> = {
    wait: "Bekle",
    selected: "Seçildi",
    eligible: "Koşullar uygun",
    rejected: "Koşullar sağlanmadı",
    blocked: "Engellendi",
    neutral: "Nötr",
  };
  if (typeof status === "string")
    return states[status] ?? "Durum açıklaması sağlanmadı";
  return "Kullanılamıyor";
}
export function paperStatusText(status: string): string {
  const known: Record<string, string> = {
    open: "Açık",
    ambiguous: "Belirsiz · açık miktar",
    cancelled_gap: "Fiyat boşluğu · iptal",
    partial: "Kısmen gerçekleşti",
    closed: "Kapalı",
    pending: "Bekliyor",
    filled: "Gerçekleşti",
    cancelled: "İptal edildi",
    expired: "Süresi doldu",
    rejected: "Reddedildi",
  };
  return known[status] ?? "Durum kodu: " + status;
}
export function transactionText(kind: string): string {
  if (kind === "entry") return "Sanal pozisyon açılışı";
  if (kind.startsWith("manual_close:")) return "Manuel sanal kapanış";
  return "İşlem kodu: " + kind;
}
export function userErrorText(
  error: unknown,
  fallback = "İşlem tamamlanamadı.",
): string {
  const profileErrors: Record<string, string> = {
    PROFILE_REVISION_CONFLICT:
      "Bu profilin daha yeni bir revizyonu var. Listeyi yenileyip son sürümü seçin.",
    PROFILE_TIMEFRAME_MISMATCH:
      "Ana analiz zaman dilimi profilin kurulum rolüyle eşleşmeli; diğer roller de istekte bulunmalı.",
    PROFILE_NOT_FOUND:
      "Bu hesapta erişilebilir profil bulunamadı. Hesabı ve seçili sürümü kontrol edin.",
    PROFILE_VERSION_UNAVAILABLE:
      "Bu profilin strateji sürümü artık desteklenmiyor. Yeni bir profil oluşturun.",
    PROFILE_HISTORY_LIMIT: "Bu profilin 64 revizyon sınırına ulaşıldı.",
    VALIDATION_ERROR:
      "Alanlar doğrulanamadı. Strateji/rejim uyumunu, zaman dilimi sırasını ve sayısal sınırları kontrol edin.",
  };
  if (
    error instanceof Error &&
    "code" in error &&
    typeof error.code === "string" &&
    profileErrors[error.code]
  )
    return profileErrors[error.code];
  if (
    error instanceof Error &&
    (error.name === "ApiError" || /[çğıöşüÇĞİÖŞÜ]/.test(error.message))
  )
    return error.message;
  return fallback;
}

export function scannerJobText(status: string) {
  return (
    (
      {
        running: "Çalışıyor",
        completed: "Tamamlandı",
        failed: "Başarısız",
        skipped_stale: "Bayat veri · atlandı",
      } as Record<string, string>
    )[status] ?? "Durum doğrulanamadı"
  );
}

// Informational lifecycle names; never imply execution or push delivery.
export function opportunityEventText(kind: unknown): string | null {
  const names: Record<string, string> = {
    opportunity_early: "Erken fırsat · teyit bekleniyor",
    opportunity_confirmed: "Fırsat koşulları teyit edildi · işlem izni değil",
    opportunity_invalidated: "Fırsat koşulu geçersizleşti",
    opportunity_expired: "Fırsatın süresi doldu",
    opportunity_unavailable: "Fırsat kaynağı kullanılamıyor",
    opportunity_recovered: "Fırsat kaynağı toparlandı · yeni teyit değil",
  };
  return typeof kind === "string" ? (names[kind] ?? null) : null;
}
