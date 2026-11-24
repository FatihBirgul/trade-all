import { useFonts } from "expo-font";

// Load Rajdhani (display / metrics) and IBM Plex Sans (body) from a CDN.
// The app never blocks on these — if the CDN is unreachable, RN falls back to
// system fonts and the UI still renders.
export const useAppFonts = (): readonly [boolean, Error | null] =>
  useFonts({
    Rajdhani: "https://cdn.jsdelivr.net/fontsource/fonts/rajdhani@latest/latin-500-normal.ttf",
    "Rajdhani-SemiBold": "https://cdn.jsdelivr.net/fontsource/fonts/rajdhani@latest/latin-600-normal.ttf",
    "Rajdhani-Bold": "https://cdn.jsdelivr.net/fontsource/fonts/rajdhani@latest/latin-700-normal.ttf",
    PlexSans: "https://cdn.jsdelivr.net/fontsource/fonts/ibm-plex-sans@latest/latin-400-normal.ttf",
    "PlexSans-Medium": "https://cdn.jsdelivr.net/fontsource/fonts/ibm-plex-sans@latest/latin-500-normal.ttf",
    "PlexSans-SemiBold": "https://cdn.jsdelivr.net/fontsource/fonts/ibm-plex-sans@latest/latin-600-normal.ttf",
  });
