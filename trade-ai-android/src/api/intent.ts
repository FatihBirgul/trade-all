// Durable mutation journal: save before network, retain on uncertain outcomes.
// The UI does not yet expose paper-order placement; this is its tested boundary.
export interface IntentStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}
export type Intent = {
  scope: string;
  path: string;
  body: Record<string, unknown>;
  idempotency_key: string;
};
export class IntentJournal {
  // One native journal key is shared across component/service instances.
  private static running = new Set<string>();
  constructor(
    private storage: IntentStorage,
    private key = "paper_intent",
  ) {}
  async pending(): Promise<Intent | null> {
    const raw = await this.storage.getItem(this.key);
    if (!raw) return null;
    const i = JSON.parse(raw);
    if (
      !i ||
      typeof i !== "object" ||
      Array.isArray(i) ||
      typeof i.scope !== "string" ||
      typeof i.path !== "string" ||
      typeof i.idempotency_key !== "string" ||
      !/^[a-zA-Z0-9_.:-]{8,128}$/.test(i.idempotency_key) ||
      !i.body ||
      typeof i.body !== "object" ||
      Array.isArray(i.body)
    )
      throw new Error("Bekleyen işlem kaydı bozuk; otomatik sıfırlanmadı.");
    return i;
  }
  async execute<T>(
    intent: Intent,
    send: (i: Intent) => Promise<T>,
  ): Promise<T> {
    if (IntentJournal.running.has(this.key))
      throw new Error("Bir işlem zaten sürüyor.");
    const proposed = JSON.parse(JSON.stringify(intent)) as Intent;
    IntentJournal.running.add(this.key);
    try {
      const previous = await this.pending();
      if (previous && JSON.stringify(previous) !== JSON.stringify(proposed))
        throw new Error("Önce bekleyen işlemin sonucunu doğrulayın.");
      if (!previous)
        await this.storage.setItem(this.key, JSON.stringify(proposed));
      // All failures retain the original key/body. Reconciliation must be explicit.
      const response = await send(previous || proposed);
      await this.storage.removeItem(this.key);
      return response;
    } finally {
      IntentJournal.running.delete(this.key);
    }
  }
}
