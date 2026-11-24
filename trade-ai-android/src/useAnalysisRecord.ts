import { useApp } from "./state";
import { useResource } from "./resource";
export function useAnalysisRecord(id: string) {
  const app = useApp();
  return useResource(async () => {
    if (app.mode === "demo")
      return app.history.find(
        (a) => a.analysis_id === id && a.data_mode === "fixture",
      );
    const record = await app.api.detail(id);
    if (record.data_mode !== "live") throw new Error("Veri modu uyuşmazlığı.");
    return record;
  }, [app.mode, id, app.connectionKey, app.config.origin, app.config.session].join("|"));
}
