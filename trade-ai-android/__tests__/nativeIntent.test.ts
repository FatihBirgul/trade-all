import * as SecureStore from "expo-secure-store";
import { IntentJournal, type Intent } from "../src/api/intent";
import { nativeIntentStorage } from "../src/api/nativeIntent";

test("belirsiz sanal işlem native depoda yeniden açılışta korunur", async () => {
  const values = new Map<string, string>();
  const get = jest
    .spyOn(SecureStore, "getItemAsync")
    .mockImplementation(async (key) => values.get(key) ?? null);
  const set = jest
    .spyOn(SecureStore, "setItemAsync")
    .mockImplementation(async (key, value) => {
      values.set(key, value);
    });
  const del = jest
    .spyOn(SecureStore, "deleteItemAsync")
    .mockImplementation(async (key) => {
      values.delete(key);
    });
  const intent: Intent = {
    scope: "gateway:AUTO",
    path: "/portfolios/AUTO/orders",
    body: { symbol: "BTCUSDT", quantity: "0.1" },
    idempotency_key: "stable-key",
  };
  const first = new IntentJournal(nativeIntentStorage);
  await expect(
    first.execute(intent, async () => {
      throw new Error("Ağ kesildi");
    }),
  ).rejects.toThrow("Ağ kesildi");
  const reopened = new IntentJournal(nativeIntentStorage);
  expect(await reopened.pending()).toEqual(intent);
  await expect(
    reopened.execute({ ...intent, idempotency_key: "new-key" }, async () => ({})),
  ).rejects.toThrow("Önce bekleyen");
  await reopened.execute(intent, async () => ({ status: "pending" }));
  expect(await reopened.pending()).toBeNull();
  get.mockRestore();
  set.mockRestore();
  del.mockRestore();
});
