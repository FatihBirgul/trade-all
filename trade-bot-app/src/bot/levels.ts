import { priceText } from "./presentation";
import type { BotPosition } from "./types";

// "1,0972" ya da "1.0972" -> sayı. Boş -> undefined (alan gönderilmez). Geçersiz -> null.
export function parsePrice(text: string): number | undefined | null {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  if (!/^[0-9]{1,12}([.,][0-9]{1,8})?$/.test(trimmed)) return null;
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) && value > 0 ? value : null;
}

// Yazım hatası süzgeci: "64.800" binlik ayraç sanılıp 64,8 olarak okunabilir, bir hane eksik
// yazılabilir. Fiyattan bu orandan fazla uzak bir seviye gönderilmez.
export const MAX_DISTANCE = 0.5;

export type LevelCheck = { ok: true; widens: boolean } | { ok: false; message: string };

// Yeni stop/hedef seviyesinin yönünü ve akla yatkınlığını denetler. Karşılaştırma anlık fiyatla (yoksa girişle).
export function checkLevel(
  kind: "sl" | "tp",
  value: number,
  position: Pick<BotPosition, "side" | "sl" | "price" | "entry">,
): LevelCheck {
  const reference = position.price ?? position.entry;
  const name = kind === "sl" ? "Stop" : "Hedef";
  if (Math.abs(value - reference) / reference > MAX_DISTANCE)
    return {
      ok: false,
      message:
        name + " " + priceText(value) + " anlık fiyattan (" + priceText(reference) +
        ") çok uzak. Yazım hatası olabilir: binlik ayraç kullanmayın, ondalık için virgül ya da nokta yazın.",
    };
  const buy = position.side === "BUY";
  const below = kind === "sl" ? buy : !buy; // AL: stop fiyatın altında, hedef üstünde. SAT: tersi.
  if (below ? value >= reference : value <= reference)
    return { ok: false, message: name + " anlık fiyatın (" + priceText(reference) + ") " + (below ? "altında" : "üstünde") + " olmalı." };
  const widens = kind === "sl" && position.sl != null && (buy ? value < position.sl : value > position.sl);
  return { ok: true, widens };
}
