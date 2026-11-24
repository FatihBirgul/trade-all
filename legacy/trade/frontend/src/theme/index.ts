// Market AI design tokens — Dark-First Utility (Personality 7).
// Single source of truth for colors, typography, spacing, radius.

export const colors = {
  surface: "#090B0F",
  onSurface: "#F3F4F6",
  surfaceSecondary: "#12161E",
  onSurfaceSecondary: "#D1D5DB",
  surfaceTertiary: "#1C222F",
  onSurfaceTertiary: "#9CA3AF",
  surfaceInverse: "#FFFFFF",
  onSurfaceInverse: "#000000",

  brand: "#EAB308",
  brandSecondary: "#FDE047",
  onBrand: "#090B0F",
  brandTertiary: "#423202",
  onBrandTertiary: "#FDE047",

  success: "#00E676",
  onSuccess: "#000000",
  warning: "#F59E0B",
  error: "#FF3B30",
  onError: "#FFFFFF",
  info: "#9CA3AF",

  border: "#272E3F",
  borderStrong: "#374151",
  divider: "#1C222F",
};

export const fonts = {
  display: "Rajdhani",
  displaySemi: "Rajdhani-SemiBold",
  displayBold: "Rajdhani-Bold",
  body: "PlexSans",
  bodyMedium: "PlexSans-Medium",
  bodySemi: "PlexSans-SemiBold",
};

export const type = {
  sm: 12,
  base: 14,
  lg: 16,
  xl: 20,
  "2xl": 24,
  "3xl": 32,
  "4xl": 44,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  "2xl": 32,
  "3xl": 48,
};

export const radius = {
  sm: 6,
  md: 12,
  lg: 20,
  pill: 999,
};

export const directionColor = (d?: string) => {
  if (d === "bullish") return colors.success;
  if (d === "bearish") return colors.error;
  return colors.onSurfaceTertiary;
};

export const changeColor = (v?: number) => {
  if (v === undefined || v === null) return colors.onSurfaceTertiary;
  if (v > 0) return colors.success;
  if (v < 0) return colors.error;
  return colors.onSurfaceTertiary;
};

// Crypto logo CDN (transparent color PNGs by ticker).
export const logoUrl = (base: string) =>
  `https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/${base.toLowerCase()}.png`;
