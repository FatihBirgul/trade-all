import React, { useEffect, useState } from "react";
import { AppState } from "react-native";
import { router } from "expo-router";
import { linkedAnalysis, uniqueRecords } from "../src/domain/records";
import { opportunityEventText } from "../src/domain/presentation";
import { NotificationPreferences } from "../src/NotificationPreferences";
import { usePage } from "../src/usePage";
import { useApp } from "../src/state";
import { useResource } from "../src/resource";
import { Button, Card, Empty, Failure, Label, Loading, Page } from "../src/ui";
export default function Notifications() {
  const app = useApp();
  const page = usePage(
    [app.mode, app.connectionKey, app.config.session].join("|"),
  );
  const { offset } = page;
  const q = useResource(
    async () => (app.mode === "demo" ? [] : app.api.notifications(offset)),
    app.mode +
      "|" +
      app.config.origin +
      "|" +
      app.config.session +
      "|" +
      app.connectionKey +
      "|" +
      offset,
  );
  return (
    <Page mode={app.mode} connection={app} headerShown>
      <NotificationPreferences
        key={[app.account, app.connectionKey].join("|")}
      />
      <Label muted>
        {app.mode === "demo"
          ? "DEMO · gerçek bildirim kuyruğu sorgulanmaz."
          : "Sunucudaki bekleyen bildirim kuyruğu · Android push değildir."}
      </Label>
      <Button
        title="Bildirimleri yenile"
        secondary
        disabled={app.mode === "demo" || q.loading}
        onPress={() => {
          page.reset();
          q.reload();
        }}
      />
      {q.loading ? (
        <Loading />
      ) : q.error ? (
        <Failure message={q.error} retry={q.reload} />
      ) : q.data?.length ? (
        uniqueRecords(q.data, (n) => n.notification_id).map((n) => (
          <Card key={n.notification_id}>
            <Label>
              {opportunityEventText(n.details.change_kind) ??
                (n.details.change_kind === "source_unavailable"
                  ? "Takip verisi geçerli değil"
                  : n.details.change_kind === "source_recovered"
                    ? "Takip verisi yeniden kullanılabilir"
                    : n.kind === "analysis"
                      ? n.details.tracking_id
                        ? "Takipte koşul değişikliği"
                        : "Analiz bildirimi"
                      : "Bildirim türü: " + n.kind)}
            </Label>
            <Label muted>
              {new Date(n.created_at_ms).toLocaleString("tr-TR")}
            </Label>
            <DeliveryStatus expires={n.details.expires_at_ms} />
            {linkedAnalysis(n.details) ? (
              <Button
                title="İlgili analizi aç"
                secondary
                onPress={() =>
                  router.push({
                    pathname: n.details.tracking_id ? "/result" : "/detail",
                    params: { id: linkedAnalysis(n.details)! },
                  })
                }
              />
            ) : null}
          </Card>
        ))
      ) : (
        <Empty
          text={
            app.mode === "demo"
              ? "Yerel DEMO’da bildirim örneği yok; sunucunun bildirim durumu bilinmiyor."
              : "Sunucu bu sayfa için boş bildirim listesi döndürdü."
          }
        />
      )}
      <Button
        title="Önceki"
        secondary
        disabled={app.mode === "demo" || q.loading || !offset}
        onPress={page.previous}
      />
      <Button
        title="Sonraki"
        secondary
        disabled={
          app.mode === "demo" ||
          q.loading ||
          !!q.error ||
          (q.data?.length || 0) < 20
        }
        onPress={page.next}
      />
    </Page>
  );
}

function DeliveryStatus({ expires }: { expires: unknown }) {
  const [now, setNow] = useState(Date.now);
  const valid =
    typeof expires === "number" && Number.isSafeInteger(expires) && expires > 0;
  useEffect(() => {
    const timer =
      valid && expires > now
        ? setTimeout(
            () => setNow(Date.now()),
            Math.min(expires - now + 1, 2147483647),
          )
        : undefined;
    const subscription = AppState.addEventListener("change", () =>
      setNow(Date.now()),
    );
    return () => {
      clearTimeout(timer);
      subscription.remove();
    };
  }, [expires, now, valid]);
  return (
    <Label>
      {valid && expires <= now
        ? "Uyarının geçerlilik süresi doldu · Gönderilmedi"
        : "Teslim bekliyor · Gönderilmedi"}
    </Label>
  );
}
