import React, { useRef, useState } from "react";
import * as Crypto from "expo-crypto";
import { useApp } from "./state";
import { useResource } from "./resource";
import { Card, Heading, Label, Button, Loading, Failure, Row } from "./ui";
import { ApiError } from "./api/client";
import { userErrorText } from "./domain/presentation";
import type { components } from "./api/schema";
type Prefs = components["schemas"]["NoticePreferences"];
type Write = components["schemas"]["NoticePreferencesWrite"];
export function NotificationPreferences() {
  const app = useApp();
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("notification-controls-v1") &&
    app.sessionInfo.accounts.includes(app.account) &&
    app.sessionInfo.scopes.includes("read");
  const q = useResource(
    async () =>
      supported ? app.api.notificationPreferences(app.account) : null,
    [app.account, app.connectionKey, app.config.session, supported].join("|"),
  );
  if (!supported)
    return (
      <Card>
        <Heading>Bildirim tercihleri</Heading>
        <Label>
          Güncel Gateway ve hesap okuma yetkisi gerekir. Push yapılandırılmış
          sayılmadı.
        </Label>
      </Card>
    );
  return (
    <Card>
      <Heading>{app.account} · bildirim tercihleri</Heading>
      <Label>
        Push servisi yapılandırılmamış. Tercih kaydı cihaz token kaydı,
        gönderici başlatma veya teslimat değildir.
      </Label>
      {q.loading ? <Loading /> : null}
      {q.error ? <Failure message={q.error} retry={q.reload} /> : null}
      {q.data && !q.loading && !q.stale ? (
        <Editor
          key={[app.account, app.config.session, q.data.revision].join("|")}
          value={q.data}
          reload={q.reload}
        />
      ) : null}
    </Card>
  );
}
function Editor({ value, reload }: { value: Prefs; reload: () => void }) {
  const app = useApp();
  const [enabled, setEnabled] = useState(value.enabled),
    [categories, setCategories] = useState(value.categories),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [uncertain, setUncertain] = useState(false);
  const pending = useRef<Write | null>(null);
  const writable = !!app.sessionInfo?.scopes.includes("notifications:write");
  const disabled = busy || uncertain || !writable;
  async function save(action: "keep" | "replace" | "revoke" = "keep") {
    if (busy || !writable) return;
    const request = pending.current ?? {
      idempotency_key: Crypto.randomUUID(),
      expected_revision: value.revision,
      enabled,
      categories,
      recipient_action: action,
    };
    pending.current = request;
    setBusy(true);
    setError("");
    try {
      await app.api.setNotificationPreferences(app.account, request);
      pending.current = null;
      setUncertain(false);
      reload();
    } catch (e) {
      const unknown = e instanceof ApiError && e.uncertain;
      setUncertain(unknown);
      if (!unknown) pending.current = null;
      setError(userErrorText(e));
      if (e instanceof ApiError && e.code === "NOTIFICATION_REVISION_CONFLICT")
        reload();
    } finally {
      setBusy(false);
    }
  }
  const status = {
    not_registered: "Kayıt yok",
    active: "Aktif mantıksal alıcı · push değil",
    revoked: "İptal edilmiş",
    expired: "Süresi dolmuş",
  }[value.recipient_status];
  return (
    <>
      <Row
        name="Sunucu durumu"
        value={value.push_status ?? "Durum doğrulanamadı"}
      />
      <Row name="Alıcı" value={status} />
      <Label muted>
        Son sunucu gözlemi:{" "}
        {typeof value.observed_at_ms === "number" &&
        value.observed_at_ms >= 0 &&
        value.observed_at_ms <= 253402300799999
          ? new Date(value.observed_at_ms).toISOString()
          : "Zaman doğrulanamadı"}
        . Alıcı durumu bu gözleme aittir.
      </Label>
      <Row name="Tercih revizyonu" value={String(value.revision)} />
      <Label muted>
        Bu ayarlar yalnız oturum ailesinin bu hesaptaki alıcısına aittir.
        Yeniden eşleştirme başka alıcıdır. Kaynak uyarısı için takip tercihi de
        açık olmalıdır.
      </Label>
      {!writable ? (
        <Label>
          Bu oturumda notifications:write izni yok; yalnız okunabilir.
        </Label>
      ) : null}
      <Button
        title={enabled ? "Bildirim tercihi: Açık" : "Bildirim tercihi: Kapalı"}
        disabled={disabled}
        onPress={() => setEnabled(!enabled)}
      />
      {(["analysis", "source", "risk", "system"] as const).map((key) => (
        <Button
          key={key}
          title={
            {
              analysis: "Analiz",
              source: "Kaynak",
              risk: "Risk",
              system: "Sistem",
            }[key] +
            ": " +
            (categories[key] ? "Açık" : "Kapalı")
          }
          disabled={disabled}
          onPress={() =>
            setCategories({ ...categories, [key]: !categories[key] })
          }
        />
      ))}
      {error ? <Label>{error}</Label> : null}
      <Button
        title={
          uncertain
            ? "Aynı tercih isteğini yeniden dene"
            : "Bildirim tercihlerini kaydet"
        }
        disabled={busy || !writable}
        onPress={() => save()}
      />
      <Button
        title="Mantıksal alıcıyı yenile"
        disabled={disabled}
        onPress={() => save("replace")}
      />
      <Button
        title="Alıcı kaydını iptal et"
        disabled={disabled}
        onPress={() => save("revoke")}
      />
      <Label muted>
        NOT_CONFIGURED teslim edilmiş demek değildir. Gerçek cihaz/provider
        kimlik bilgileri desteklenmiyor; token gönderilmez.
      </Label>
    </>
  );
}
