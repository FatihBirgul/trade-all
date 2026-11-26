// Tasarım yönü C ("Canlı"): renkli üst alan, yuvarlak beyaz kartlar, iri başlıklar.
export const c = {
  bg: "#F2F3FA",
  hero: "#2A2D7C",
  heroSoft: "#3D41A6",
  heroText: "#B9BCE8",
  tint: "#E8E9FB",
  card: "#FFFFFF",
  text: "#16183A",
  muted: "#7A7F9D",
  line: "#E6E8F4",
  up: "#12A873",
  upSoft: "#DFF6EC",
  down: "#E5484D",
  downSoft: "#FDE8E8",
  sun: "#B7791F",
  sunSoft: "#FFF3D6",
  white: "#FFFFFF",
} as const;

export const tone = (value: number | null | undefined) =>
  value == null || value === 0 ? c.text : value > 0 ? c.up : c.down;
export const soft = (value: number | null | undefined) =>
  value == null || value === 0 ? c.line : value > 0 ? c.upSoft : c.downSoft;

export const shadow = {
  shadowColor: c.hero,
  shadowOpacity: 0.08,
  shadowRadius: 18,
  shadowOffset: { width: 0, height: 8 },
  elevation: 3,
} as const;
