import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import type { BotConfig } from "./types";

const KEY = "trade_bot";

function valid(value: unknown): value is BotConfig {
  const config = value as BotConfig | null;
  return (
    !!config &&
    typeof config.origin === "string" &&
    config.origin.startsWith("https://") &&
    typeof config.token === "string" &&
    config.token.length >= 32 &&
    typeof config.pairedAt === "number"
  );
}

// Token yalnızca cihazın güvenli deposunda tutulur; web'de kalıcı saklanmaz.
export async function loadBotConfig(): Promise<BotConfig | null> {
  if (Platform.OS === "web") return null;
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    return valid(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export async function saveBotConfig(config: BotConfig): Promise<void> {
  if (Platform.OS === "web") return;
  await SecureStore.setItemAsync(KEY, JSON.stringify(config));
}

export async function clearBotConfig(): Promise<void> {
  if (Platform.OS === "web") return;
  try {
    await SecureStore.deleteItemAsync(KEY);
  } catch {
    // Silinemese bile bellekteki bağlantı kapatılır.
  }
}
