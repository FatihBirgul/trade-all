import { ApiError, type createApi } from "./client";
import type { IntentStorage } from "./intent";
type API = ReturnType<typeof createApi>;
type Pending = { scope: string; lastTick: number | null; knownJobs: string[] };
const KEY = "scanner_tick_pending";
export class ScannerJournal {
  private static running = false;
  constructor(
    private storage: IntentStorage,
    private scope: string,
  ) {}
  async pending(): Promise<Pending | null> {
    const raw = await this.storage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (
      !value ||
      value.scope !== this.scope ||
      !(value.lastTick === null || Number.isSafeInteger(value.lastTick)) ||
      !Array.isArray(value.knownJobs) ||
      value.knownJobs.length > 20 ||
      !value.knownJobs.every((id: unknown) => typeof id === "string")
    )
      throw new Error(
        "Bekleyen tarama başka cihaz/gateway’e ait veya kayıt doğrulanamadı. Otomatik sıfırlanmadı.",
      );
    return value;
  }
  async execute(api: API) {
    if (ScannerJournal.running) throw new Error("Tarama isteği zaten sürüyor.");
    ScannerJournal.running = true;
    try {
      if (await this.pending())
        throw new Error(
          "Önce bekleyen taramayı kontrol edin. Yeni tarama gönderilmedi.",
        );
      const [state, jobs] = await Promise.all([api.scanner(), api.jobs()]);
      if (state.lease_id)
        throw new Error("Sunucuda tarama zaten sürüyor. Durumu yenileyin.");
      await this.storage.setItem(
        KEY,
        JSON.stringify({
          scope: this.scope,
          lastTick: state.last_tick_ms,
          knownJobs: jobs.map((j) => j.job_id),
        }),
      );
      try {
        const result = await api.tick();
        await this.storage.removeItem(KEY);
        return result;
      } catch (error) {
        if (
          error instanceof ApiError &&
          !error.uncertain &&
          error.status >= 400 &&
          error.status < 500
        )
          await this.storage.removeItem(KEY);
        throw error;
      }
    } finally {
      ScannerJournal.running = false;
    }
  }
  async reconcile(api: API) {
    const pending = await this.pending();
    if (!pending) return { confirmed: true, message: "Bekleyen tarama yok." };
    const [state, jobs] = await Promise.all([api.scanner(), api.jobs()]);
    const advanced =
      state.last_tick_ms !== null &&
      (pending.lastTick === null || state.last_tick_ms > pending.lastTick);
    if (!advanced || state.lease_id)
      return {
        confirmed: false,
        message: state.lease_id
          ? "Tarama sunucuda devam ediyor. Yeni istek gönderilmedi."
          : "Sonuç henüz kayıtlarla doğrulanamadı. Yeni tarama gönderilmedi; tekrar kontrol edin.",
      };
    const rows = jobs.filter(
      (j) =>
        !pending.knownJobs.includes(j.job_id) &&
        (j.started_at_ms ?? 0) >= state.last_tick_ms!,
    );
    if (rows.some((j) => j.status === "running"))
      return {
        confirmed: false,
        message: "Analiz işleri devam ediyor. Yeni tarama gönderilmedi.",
      };
    await this.storage.removeItem(KEY);
    return {
      confirmed: true,
      message: state.last_error
        ? "Tarama döngüsü sunucuda engellendi; iş kayıtlarını kontrol edin."
        : rows.length
          ? "Sunucu kayıtları doğrulandı: " +
            rows.filter((j) => j.status === "completed").length +
            " tamamlanan / " +
            rows.filter((j) => j.status === "failed").length +
            " başarısız analiz. Yeniden tarama gönderilmedi."
          : "Sunucudaki tarama döngüsü tamamlanmış. Yeni iş yok; aynı mumdaki işler tekrarlanmaz.",
    };
  }
}
