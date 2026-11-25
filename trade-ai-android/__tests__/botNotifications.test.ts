import {
  heartbeatNotifier,
  importantKinds,
  isImportant,
  kindLabel,
  notifyNewEvents,
  registerPush,
} from "../src/bot/notifications";
import type { BotEvent } from "../src/bot/types";

const event = (id: number, kind: string, level = "info"): BotEvent => ({
  id,
  at: 1_800_000_000 + id,
  level,
  kind,
  message: "mesaj " + id,
  data: null,
});

test("only important kinds notify", () => {
  const schedule = jest.fn();
  const seen = notifyNewEvents(
    [event(1, "scan"), event(2, "trade_opened"), event(3, "signal"), event(4, "sl_missing", "error")],
    0,
    schedule,
  );
  expect(seen).toBe(4);
  expect(schedule.mock.calls).toEqual([
    ["İşlem açıldı", "mesaj 2"],
    ["Stop eksik", "mesaj 4"],
  ]);
  for (const kind of [
    "trade_opened",
    "trade_closed",
    "sl_breakeven",
    "sl_missing",
    "tp_lost",
    "daily_limit",
    "bot_halted",
    "connection_lost",
    "order_rejected",
    "auth_error",
    "news_unavailable",
    "strategy_paused",
  ])
    expect(importantKinds.has(kind)).toBe(true);
  expect(importantKinds.has("scan")).toBe(false);
});

test("does not renotify seen events", () => {
  const schedule = jest.fn();
  const batch = [event(6, "trade_closed"), event(5, "trade_opened")]; // sıra karışık gelebilir
  const seen = notifyNewEvents(batch, 5, schedule);
  expect(seen).toBe(6);
  expect(schedule).toHaveBeenCalledTimes(1);
  expect(notifyNewEvents(batch, seen, schedule)).toBe(6);
  expect(schedule).toHaveBeenCalledTimes(1);
  expect(notifyNewEvents([], 6, schedule)).toBe(6);
});

test("a failing notification never breaks the event flow", () => {
  const throwing = jest.fn(() => {
    throw new Error("izin yok");
  });
  const rejecting = jest.fn().mockRejectedValue(new Error("izin yok"));
  expect(notifyNewEvents([event(1, "trade_opened"), event(2, "trade_closed")], 0, throwing)).toBe(2);
  expect(notifyNewEvents([event(1, "trade_opened")], 0, rejecting)).toBe(1);
  expect(throwing).toHaveBeenCalledTimes(2);
});

test("heartbeat loss notifies once until recovered", () => {
  const schedule = jest.fn();
  const update = heartbeatNotifier(schedule);
  update(false);
  expect(schedule).not.toHaveBeenCalled();
  update(true);
  update(true);
  update(true);
  expect(schedule).toHaveBeenCalledTimes(1);
  expect(schedule.mock.calls[0][0]).toBe("Bottan 5 dakikadır haber yok");
  update(false);
  update(true);
  expect(schedule).toHaveBeenCalledTimes(2);
});

test("registerPush posts token when available and returns false otherwise", async () => {
  const api = { registerDevice: jest.fn().mockResolvedValue({ registered: true }) };
  await expect(registerPush(api, async () => "ExponentPushToken[abc]")).resolves.toBe(true);
  expect(api.registerDevice).toHaveBeenCalledWith("ExponentPushToken[abc]");
  await expect(registerPush(api, async () => null)).resolves.toBe(false);
  await expect(
    registerPush(api, async () => {
      throw new Error("FCM yapılandırılmamış");
    }),
  ).resolves.toBe(false);
  expect(api.registerDevice).toHaveBeenCalledTimes(1);
  api.registerDevice.mockRejectedValue(new Error("ağ"));
  await expect(registerPush(api, async () => "ExponentPushToken[abc]")).resolves.toBe(false);
});

test("labels and importance", () => {
  expect(kindLabel("trade_closed")).toBe("İşlem kapandı");
  expect(kindLabel("yeni_bir_tur")).toBe("yeni_bir_tur"); // bilinmeyen tür gizlenmez
  expect(isImportant({ kind: "scan", level: "info" })).toBe(false);
  expect(isImportant({ kind: "rate_limited", level: "warning" })).toBe(true);
  expect(isImportant({ kind: "trade_opened", level: "info" })).toBe(true);
});

test("old events are summarised and at most three are announced individually", () => {
  const now = 1_800_000_000 + 10_000;
  const old = Array.from({ length: 6 }, (_, i) => ({ ...event(i + 1, "trade_opened"), at: now - 7200 }));
  const fresh = Array.from({ length: 5 }, (_, i) => ({ ...event(i + 10, "trade_closed"), at: now - 30 }));
  const schedule = jest.fn();
  expect(notifyNewEvents([...old, ...fresh, { ...event(20, "scan"), at: now }], 0, schedule, now)).toBe(20);
  expect(schedule.mock.calls.map(([title, body]) => [title, body.slice(0, 8)])).toEqual([
    ["İşlem kapandı", "mesaj 12"],
    ["İşlem kapandı", "mesaj 13"],
    ["İşlem kapandı", "mesaj 14"],
    ["8 önemli olay daha", "Uygulama"],
  ]);
  const quiet = jest.fn();
  notifyNewEvents([{ ...event(30, "trade_opened"), at: now - 5 }], 20, quiet, now);
  expect(quiet).toHaveBeenCalledTimes(1); // tek yeni olay: özet yok
});
