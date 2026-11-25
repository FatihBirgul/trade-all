// Ayarlar formunun saf mantığı: doğrulama, eski → yeni fark listesi ve riskin artıp artmadığı.
import type { BotSettings } from "./types";

export type Draft = {
  risk_pct: string;
  max_open_bot: string;
  daily_loss_pct: string;
  total_loss_pct: string;
  news_enabled: boolean;
  news_window: string;
  fusion_enabled: boolean;
  min_score: string;
};

type Field = {
  key: keyof Draft;
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

export const NUMBER_FIELDS: Field[] = [
  { key: "risk_pct", label: "İşlem başı risk", min: 0.25, max: 1, unit: "%", riskier: "up",
    read: (s) => s.risk.risk_pct, write: (s, v) => { s.risk.risk_pct = v; } },
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
];

const text = (value: number) => String(value).replace(".", ",");

export function draftFrom(settings: BotSettings): Draft {
  return {
    risk_pct: text(settings.risk.risk_pct),
    max_open_bot: text(settings.risk.max_open_bot),
    daily_loss_pct: text(settings.risk.daily_loss_pct),
    total_loss_pct: text(settings.risk.total_loss_pct),
    news_enabled: settings.news.enabled,
    news_window: text(settings.news.window_minutes),
    fusion_enabled: settings.fusion.enabled,
    min_score: text(settings.fusion.min_score),
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
export function planChanges(current: BotSettings, draft: Draft): Plan {
  const changes: Change[] = [];
  const writers: ((settings: BotSettings) => void)[] = [];
  for (const field of NUMBER_FIELDS) {
    const value = parse(draft[field.key] as string);
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
  const mid = current.fusion.mid_score;
  const minScore = parse(draft.min_score);
  if (minScore !== null && minScore > mid)
    return { ok: false, error: "En düşük güven puanı orta eşikten (" + text(mid) + ") büyük olamaz." };
  for (const [key, label, read, write] of [
    ["news_enabled", "Haber penceresi koruması", (s: BotSettings) => s.news.enabled,
      (s: BotSettings, v: boolean) => { s.news.enabled = v; }],
    ["fusion_enabled", "Güven puanı", (s: BotSettings) => s.fusion.enabled,
      (s: BotSettings, v: boolean) => { s.fusion.enabled = v; }],
  ] as const) {
    const value = draft[key];
    const before = read(current);
    if (value === before) continue;
    // Bir korumayı kapatmak riski artırır.
    changes.push({ label, from: before ? "Açık" : "Kapalı", to: value ? "Açık" : "Kapalı", riskier: !value });
    writers.push((settings) => {
      if (read(settings) !== before) throw new Error(CHANGED);
      write(settings, value);
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
  };
  return names[id] ?? id;
}
