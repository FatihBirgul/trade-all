import React, { useRef, useState } from "react";
import { useApp } from "./state";
import { useResource } from "./resource";
import { Button, Label } from "./ui";
import { ApiError } from "./api/client";
import { userErrorText } from "./domain/presentation";
export function FollowPolicyControls({
  id,
  account,
}: {
  id: string;
  account: "AUTO" | "MANUAL";
}) {
  const app = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [uncertain, setUncertain] = useState(false);
  const pending = useRef<boolean | null>(null);
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("follow-source-events-v1") &&
    !!app.sessionInfo.accounts.includes(account);
  const q = useResource(async () => {
    if (!supported) return null;
    const data = await app.api.followPolicy(id);
    if (data.portfolio_id !== account || data.tracking_id !== id)
      throw new ApiError("INVALID_RESPONSE");
    return data;
  }, [app.mode, app.connectionKey, app.config.session, id, account, supported].join("|"));
  if (!supported) return null;
  async function save() {
    if (busy || !q.data || !app.sessionInfo?.scopes.includes("scanner:write"))
      return;
    const desired = pending.current ?? !q.data.notify_source_changes;
    pending.current = desired;
    setBusy(true);
    setError("");
    try {
      await app.api.setFollowPolicy(id, desired);
      pending.current = null;
      setUncertain(false);
      q.reload();
    } catch (e) {
      const unknown = e instanceof ApiError && e.uncertain;
      setUncertain(unknown);
      if (!unknown) pending.current = null;
      setError(userErrorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Label>
        Kaynak/kalite/geçerlilik uyarıları:{" "}
        {q.loading
          ? "Kontrol ediliyor…"
          : q.error
            ? "Doğrulanamadı"
            : q.data?.notify_source_changes
              ? "Açık"
              : "Kapalı"}
      </Label>
      {q.error ? <Label>{q.error}</Label> : null}
      {error ? <Label>{error}</Label> : null}
      <Label muted>
        Bu tercih yalnız sunucu kuyruğuna kesinti ve toparlanma uyarısı ekler.
        İşçiyi başlatmaz, emir vermez ve Android push teslimatı sağlamaz.
      </Label>
      {app.sessionInfo?.scopes.includes("scanner:write") ? (
        <Button
          title={
            busy
              ? "Tercih kaydediliyor…"
              : uncertain
                ? "Aynı tercihi yeniden dene"
                : q.data?.notify_source_changes
                  ? "Kaynak uyarılarını kapat"
                  : "Kaynak uyarılarını aç"
          }
          disabled={busy || q.loading || !!q.error || !q.data}
          onPress={save}
        />
      ) : (
        <Label muted>
          Bu tercihi değiştirmek için hesabın scanner yazma yetkisi gerekir.
        </Label>
      )}
    </>
  );
}
