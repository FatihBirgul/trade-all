// expo-notifications ile cihaz tarafı. Kurallar notifications.ts içindedir.
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

// Sunucunun uzak bildirimlerde kullandığı kanal ile aynı olmalı (tradebot/notify/expo.py).
const CHANNEL = "default";
let prepared: Promise<boolean> | null = null;

async function setup(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
  if (Platform.OS === "android")
    await Notifications.setNotificationChannelAsync(CHANNEL, {
      name: "Trade Bot",
      importance: 6, // AndroidImportance.HIGH: ekranda açılan bildirim
    });
  let permission = await Notifications.getPermissionsAsync();
  if (!permission.granted && permission.canAskAgain) permission = await Notifications.requestPermissionsAsync();
  return permission.granted;
}

// İzin ve kanal bir kez hazırlanır; izin verilmezse bildirimler sessizce atlanır.
export function prepare(): Promise<boolean> {
  prepared ??= setup().catch(() => false);
  return prepared;
}

export async function schedule(title: string, body: string): Promise<void> {
  if (!(await prepare())) return;
  await Notifications.scheduleNotificationAsync({ content: { title, body }, trigger: { channelId: CHANNEL } });
}

// Expo push token: yalnızca Expo proje kimliği ve FCM yapılandırılmışsa alınabilir.
export async function pushToken(): Promise<string | null> {
  const projectId: unknown = Constants.expoConfig?.extra?.eas?.projectId;
  if (typeof projectId !== "string" || !projectId) return null;
  if (!(await prepare())) return null;
  return (await Notifications.getExpoPushTokenAsync({ projectId })).data;
}
