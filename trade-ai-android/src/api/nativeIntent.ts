import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import type { IntentStorage } from "./intent";

// Use only on native. An incomplete paper operation stays encrypted on the device
// until the server outcome is reconciled; the UI must never clear it optimistically.
export const nativeIntentStorage: IntentStorage = {
  async getItem(key) {
    if (Platform.OS === "web") throw new Error("Native işlem günlüğü web ortamında kapalı.");
    return SecureStore.getItemAsync(key);
  },
  async setItem(key, value) {
    if (Platform.OS === "web") throw new Error("Native işlem günlüğü web ortamında kapalı.");
    await SecureStore.setItemAsync(key, value);
  },
  async removeItem(key) {
    if (Platform.OS === "web") throw new Error("Native işlem günlüğü web ortamında kapalı.");
    await SecureStore.deleteItemAsync(key);
  },
};
