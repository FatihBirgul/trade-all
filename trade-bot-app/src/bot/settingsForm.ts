// Ayarlar formunun saf mantığı: doğrulama, eski → yeni fark listesi ve riskin artıp artmadığı.
import type { BotSettings } from "./types";

export type Draft = {
  risk_pct: string;
  max_spread_stop_pct: string;
  max_open_bot: string;
  daily_loss_pct: string;
  total_loss_pct: string;
  news_enabled: boolean;
  news_window: string;
  fusion_enabled: boolean;
  min_score: string;
  mid_score: string;
  high_score: string;
  be_enabled: boolean;
  partial_enabled: boolean;
  trail_enabled: boolean;
  symbols: string[] | null; // null = hepsi açık
};

type NumberKey = "risk_pct" | "max_spread_stop_pct" | "max_open_bot" | "daily_loss_pct" | "total_loss_pct" | "news_window" | "min_score" | "mid_score" | "high_score";
export type ToggleKey = "news_enabled" | "fusion_enabled" | "be_enabled" | "partial_enabled" | "trail_enabled";

type Field = {
  key: NumberKey;
  label: string;
  min: number;
  max: number;
  integer?: boolean;
  unit: string;
  read: (settings: BotSettings) => number;
  write: (settings: BotSettings, value: number) => void;
  // Değer hangi yönde değişirse risk artar?
  riskier: "up" | "down";
};

export const COST_GATE_DEFAULT = 15;

export const NUMBER_FIELDS: Field[] = [
  { key: "risk_pct", label: "İşlem başı risk", min: 0.25, max: 1, unit: "%", riskier: "up",
    read: (s) => s.risk.risk_pct, write: (s, v) => { s.risk.risk_pct = v; } },
  // Maliyet kapısı: giriş anındaki alış-satış farkı stop mesafesinin bu yüzdesinden büyükse işlem açılmaz.
  // Sınır yükselirse daha pahalı işlemlere izin verilir: risk artar. Eski sunucuda alan yoktur (varsayılan 15).
  { key: "max_spread_stop_pct", label: "En çok maliyet (alış-satış farkı ÷ stop)", min: 5, max: 25, unit: "%", riskier: "up",
    read: (s) => (typeof s.risk.max_spread_stop_pct === "number" ? s.risk.max_spread_stop_pct : COST_GATE_DEFAULT),
    write: (s, v) => { s.risk.max_spread_stop_pct = v; } },
  { key: "max_open_bot", label: "Aynı anda açık bot işlemi", min: 1, max: 5, integer: true, unit: "", riskier: "up",
    read: (s) => s.risk.max_open_bot, write: (s, v) => { s.risk.max_open_bot = v; } },
  { key: "daily_loss_pct", label: "Günlük kayıp sınırı", min: 2, max: 10, unit: "%", riskier: "up",
    read: (s) => s.risk.daily_loss_pct, write: (s, v) => { s.risk.daily_loss_pct = v; } },
  { key: "total_loss_pct", label: "Toplam kayıp sınırı", min: 10, max: 30, unit: "%", riskier: "up",
    read: (s) => s.risk.total_loss_pct, write: (s, v) => { s.risk.total_loss_pct = v; } },
  { key: "news_window", label: "Haber penceresi", min: 5, max: 120, integer: true, unit: " dk", riskier: "down",
    read: (s) => s.news.window_minutes, write: (s, v) => { s.news.window_minutes = v; } },
  { key: "min_score", label: "En düşük güven puanı", min: 0, max: 100, unit: "", riskier: "down",
    read: (s) => s.fusion.min_score, write: (s, v) => { s.fusion.min_score = v; } },
  // Eşik düşerse aynı puanla daha büyük lot açılır: risk artar.
  { key: "mid_score", label: "Orta güven eşiği (altı yarım lot)", min: 0, max: 100, unit: "", riskier: "down",
    read: (s) => s.fusion.mid_score, write: (s, v) => { s.fusion.mid_score = v; } },
  { key: "high_score", label: "Yüksek güven eşiği (üstü tam lot)", min: 0, max: 100, unit: "", riskier: "down",
    read: (s) => s.fusion.high_score, write: (s, v) => { s.fusion.high_score = v; } },
];

type Toggle = { key: ToggleKey; label: string; read: (s: BotSettings) => boolean; write: (s: BotSettings, v: boolean) => void };
const manageToggle = (key: "be_enabled" | "partial_enabled" | "trail_enabled", label: string): Toggle => ({
  key,
  label,
  read: (s) => s.manage?.[key] !== false,
  write: (s, v) => {
    if (!s.manage || typeof s.manage !== "object") throw new Error("Sunucu bu ayarı desteklemiyor; sunucuyu güncelleyin.");
    s.manage[key] = v;
  },
});
// Hepsi birer korumadır: kapatmak riski artırır.
export const TOGGLES: Toggle[] = [
  { key: "news_enabled", label: "Haber penceresi koruması", read: (s) => s.news.enabled, write: (s, v) => { s.news.enabled = v; } },
  { key: "fusion_enabled", label: "Güven puanı", read: (s) => s.fusion.enabled, write: (s, v) => { s.fusion.enabled = v; } },
  manageToggle("be_enabled", "Başa baş stopu (1R’de)"),
  manageToggle("partial_enabled", "Kısmi kâr alma (2R’de)"),
  manageToggle("trail_enabled", "İz süren stop"),
];

const sameSet = (a: readonly string[] | null, b: readonly string[] | null) =>
  a === null || b === null ? a === b : a.length === b.length && a.every((item) => b.includes(item));
const symbolList = (settings: BotSettings): string[] | null =>
  Array.isArray(settings.enabled_symbols) ? [...settings.enabled_symbols].sort() : null;

const text = (value: number) => String(value).replace(".", ",");

export function draftFrom(settings: BotSettings): Draft {
  return {
    risk_pct: text(settings.risk.risk_pct),
    max_spread_stop_pct: text(typeof settings.risk.max_spread_stop_pct === "number" ? settings.risk.max_spread_stop_pct : COST_GATE_DEFAULT),
    max_open_bot: text(settings.risk.max_open_bot),
    daily_loss_pct: text(settings.risk.daily_loss_pct),
    total_loss_pct: text(settings.risk.total_loss_pct),
    news_enabled: settings.news.enabled,
    news_window: text(settings.news.window_minutes),
    fusion_enabled: settings.fusion.enabled,
    min_score: text(settings.fusion.min_score),
    mid_score: text(settings.fusion.mid_score),
    high_score: text(settings.fusion.high_score),
    be_enabled: settings.manage?.be_enabled !== false,
    partial_enabled: settings.manage?.partial_enabled !== false,
    trail_enabled: settings.manage?.trail_enabled !== false,
    symbols: symbolList(settings),
  };
}

function parse(value: string): number | null {
  const trimmed = value.trim();
  if (!/^[0-9]{1,6}([.,][0-9]{1,4})?$/.test(trimmed)) return null;
  return Number(trimmed.replace(",", "."));
}

export const CHANGED = "Ayarlar bu arada sunucuda değişmiş; kaydedilmedi. Yenileyip yeniden deneyin.";

export type Change = { label: string; from: string; to: string; riskier: boolean };
export type Plan =
  | { ok: false; error: string }
  | { ok: true; changes: Change[]; riskier: boolean; apply: (settings: BotSettings) => BotSettings };

// Taslağı güncel ayarlarla karşılaştırır. Yalnızca değişen alanlar uygulanır; diğerlerine dokunulmaz.
// `universe`: sunucunun işlem evreni (sembol seçimi için); verilirse "hepsi açık" seçimi null olarak yazılır.
export function planChanges(current: BotSettings, draft: Draft, universe?: readonly string[]): Plan {
  const changes: Change[] = [];
  const writers: ((settings: BotSettings) => void)[] = [];
  for (const field of NUMBER_FIELDS) {
    const value = parse(draft[field.key]);
    if (value === null || value < field.min || value > field.max || (field.integer && !Number.isInteger(value)))
      return {
        ok: false,
        error:
          field.label + ": " + text(field.min) + " ile " + text(field.max) + " arasında " +
          (field.integer ? "tam sayı" : "bir sayı") + " girin.",
      };
    const before = field.read(current);
    if (value === before) continue;
    changes.push({
      label: field.label,
      from: text(before) + field.unit,
      to: text(value) + field.unit,
      riskier: field.riskier === "up" ? value > before : value < before,
    });
    writers.push((settings) => {
      // Onay penceresi "eski → yeni"yi ekrandaki kopyadan gösterdi; sunucudaki değer başkaysa kullanıcı
      // yanlış bir karşılaştırmayı onaylamış olur. Yazmadan durulur.
      if (field.read(settings) !== before) throw new Error(CHANGED);
      field.write(settings, value);
    });
  }
  const [low, mid, high] = [parse(draft.min_score), parse(draft.mid_score), parse(draft.high_score)];
  if (low !== null && mid !== null && high !== null && !(low <= mid && mid <= high))
    return { ok: false, error: "Güven eşikleri sıralı olmalı: en düşük ≤ orta ≤ yüksek." };
  for (const toggle of TOGGLES) {
    const value = draft[toggle.key];
    const before = toggle.read(current);
    if (value === before) continue;
    // Bir korumayı kapatmak riski artırır.
    changes.push({ label: toggle.label, from: before ? "Açık" : "Kapalı", to: value ? "Açık" : "Kapalı", riskier: !value });
    writers.push((settings) => {
      if (toggle.read(settings) !== before) throw new Error(CHANGED);
      toggle.write(settings, value);
    });
  }
  // Semboller: evrenin tamamı seçiliyse "hepsi" (null) yazılır; yeni eklenen semboller de açık kalır.
  let wanted = draft.symbols === null ? null : [...new Set(draft.symbols)].sort();
  if (wanted !== null && wanted.length === 0) return { ok: false, error: "En az bir sembol açık olmalı. Botu durdurmak için Panel’deki Durdur’u kullanın." };
  const had = symbolList(current);
  // "Hepsi"ye çevirme yalnızca kullanıcı sembolleri GERÇEKTEN değiştirdiyse yapılır: başka bir ayarı kaydetmek,
  // sunucudaki açık listeyi (evren geçici olarak daralmış olsa bile) kendiliğinden "hepsi"ye çevirmemeli.
  if (wanted !== null && !sameSet(wanted, had) && universe && universe.length > 0 && universe.every((symbol) => wanted!.includes(symbol)))
    wanted = null;
  if (!sameSet(wanted, had)) {
    const all = universe ?? [];
    const before = had ?? all;
    const after = wanted ?? all;
    const closed = before.filter((symbol) => !after.includes(symbol));
    const opened = after.filter((symbol) => !before.includes(symbol));
    const names = (list: string[]) => list.slice(0, 8).join(", ") + (list.length > 8 ? " +" + (list.length - 8) : "");
    const count = (list: string[] | null) => (list === null ? "Hepsi" : String(list.length));
    changes.push({
      label: "Açık semboller",
      from: count(had),
      to: count(wanted) + (closed.length ? " (kapanan: " + names(closed) + ")" : "") + (opened.length ? " (açılan: " + names(opened) + ")" : ""),
      // Yeni sembol açmak (ya da listeyi "hepsi"ye çevirmek) botun işlem açabileceği alanı genişletir.
      riskier: opened.length > 0 || (wanted === null && had !== null),
    });
    const target = wanted;
    writers.push((settings) => {
      if (!sameSet(symbolList(settings), had)) throw new Error(CHANGED);
      settings.enabled_symbols = target;
    });
  }
  return {
    ok: true,
    changes,
    riskier: changes.some((change) => change.riskier),
    apply: (settings) => {
      for (const write of writers) write(settings);
      return settings;
    },
  };
}

export const MODE_LABEL = { live: "Canlı", shadow: "Gölge", off: "Kapalı" } as const;

export function strategyName(id: string): string {
  const names: Record<string, string> = {
    fx_trend_momentum_v6: "Trend momentum",
    fx_range_reversion_v6: "Bant içi dönüş",
    fx_confirmed_breakout_v6: "Onaylı kırılım",
    fx_failed_breakout_v6: "Sahte kırılım",
    tb_ema_pullback_v1: "EMA geri çekilme (yeni)",
    tb_donchian_breakout_v1: "Kanal kırılımı (yeni)",
    tb_smc_sweep_v1: "SMC süpürme (yorum)",
    tb_emapb_h1_20_21_v1: "H1 EMA 20/21 geri çekilme (yorum)",
    tb_emapb_h1_21_50_v1: "H1 EMA 21/50 geri çekilme (yorum)",
    tb_smc_day_v13: "SMC gün içi (v13)",
    tb_smc_week_v13: "SMC haftalık (v13)",
    tb_emapb_day_v13: "EMA geri çekilme gün içi (v13)",
    tb_emapb_week_v13: "EMA geri çekilme haftalık (v13)",
    tb_week_trade_v1: "Week trade",
  tb_week_trade_v1_orig6: "Week trade · özgün 6 sembol (kıyas)",
    tb_silver_bullet_v1: "ICT Silver Bullet",
    tb_asia_london_v1: "Asya aralığı / Londra kırılımı",
    tb_turtle55_v1: "Günlük trend takibi (55/20)",
  };
  return names[id] ?? id;
}
