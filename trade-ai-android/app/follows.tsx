import React, { useEffect, useRef, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useApp } from "../src/state";
import { useResource } from "../src/resource";
import {
  allowedFollows,
  latestFollowChange,
  loadFollowChanges,
  type Follow,
} from "../src/domain/follows";
import {
  directionText,
  reasonText,
  userErrorText,
} from "../src/domain/presentation";
import {
  Button,
  Card,
  Choices,
  Empty,
  Failure,
  Heading,
  Label,
  Loading,
  Page,
  Row,
} from "../src/ui";
const stamp = (v: number | null) =>
  v ? new Date(v).toLocaleString("tr-TR") : "Henüz kontrol edilmedi";
export default function Follows() {
  const app = useApp();
  const { analysis: selectedAnalysis } = useLocalSearchParams<{
    analysis?: string;
  }>();
  const scope = [
    app.mode,
    app.config.origin,
    app.config.session,
    app.connectionKey,
  ].join("|");
  const current = useRef(scope),
    locked = useRef(false);
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState({ scope: "", text: "" });
  const [filter, setFilter] = useState("Tümü"),
    [limit, setLimit] = useState(20);
  const [startOpen, setStartOpen] = useState(!!selectedAnalysis),
    [changesOpen, setChangesOpen] = useState(false);
  useEffect(() => {
    current.current = scope;
  }, [scope]);
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    app.sessionInfo?.capabilities?.includes("analysis-follow-v1");
  const canWrite =
    !!supported && app.sessionInfo?.scopes.includes("scanner:write");
  const q = useResource(
    async () => ({
      rows: supported
        ? allowedFollows(
            await app.api.follows(),
            app.sessionInfo?.accounts ?? [],
          )
        : [],
      checkedAt: Date.now(),
    }),
    scope + "|" + supported,
  );
  const candidates = useResource(
    async () =>
      startOpen && supported
        ? (selectedAnalysis && /^[a-f0-9]{64}$/.test(selectedAnalysis)
            ? [await app.api.detail(selectedAnalysis)]
            : await app.api.analyses()
          )
            .filter(
              (a) =>
                a.data_mode === "live" &&
                app.sessionInfo?.accounts.includes(a.risk_portfolio),
            )
            .slice(0, 8)
        : [],
    scope + "|" + startOpen + "|" + supported + "|" + selectedAnalysis,
  );
  const changes = useResource(
    async () => (changesOpen && supported ? loadFollowChanges(app.api) : []),
    scope + "|" + changesOpen + "|" + supported,
  );
  async function mutate(operation: () => Promise<unknown>) {
    if (!canWrite || locked.current || q.loading || q.error) return;
    locked.current = true;
    setBusy(true);
    const attempted = scope;
    setMessage({ scope: attempted, text: "" });
    try {
      await operation();
    } catch (error) {
      if (current.current === attempted)
        setMessage({
          scope: attempted,
          text:
            userErrorText(error) +
            " Durum yeniden sorgulanıyor; işlem otomatik tekrarlanmadı.",
        });
    } finally {
      if (current.current === attempted) {
        q.reload();
        if (changesOpen) changes.reload();
      }
      locked.current = false;
      setBusy(false);
    }
  }
  const rows =
    q.data?.rows.filter(
      (r) =>
        filter === "Tümü" ||
        (filter === "Aktif" ? r.enabled : r.portfolio_id === filter),
    ) ?? [];
  return (
    <Page mode={app.mode} connection={app} headerShown>
      <Heading>Analiz takipleri</Heading>
      {app.mode === "demo" ? (
        <Empty text="Takip yönetimi CANLI bağlantıda kullanılabilir. DEMO'da PC işçisi çalıştırılmaz." />
      ) : !supported ? (
        <Empty text="Bağlantıyı doğrulayın. Bu özellik güncel Gateway ve Backend gerektirir." />
      ) : (
        <>
          <Label muted>
            {q.data?.rows.filter((r) => r.enabled).length ?? "—"} aktif · en çok
            6 aktif / 100 toplam · hesaplar ayrı
          </Label>
          <Choices
            values={["Tümü", "Aktif", ...(app.sessionInfo?.accounts ?? [])]}
            value={filter}
            onChange={(v) => {
              setFilter(v);
              setLimit(20);
            }}
          />
          <Button
            title="Takipleri yenile"
            secondary
            disabled={busy || q.loading}
            onPress={q.reload}
          />
          {q.loading ? (
            <Loading />
          ) : q.error ? (
            <Failure
              message={
                "Bağlantı yok · takip/işçi durumu doğrulanamadı. " + q.error
              }
              retry={q.reload}
            />
          ) : !rows.length ? (
            <Empty text="Bu filtrede takip yok. Bir analiz sonucundan veya aşağıdan takip başlatabilirsiniz." />
          ) : (
            rows.slice(0, limit).map((track: Follow) => {
              const change = latestFollowChange(changes.data ?? [], track);
              return (
                <Card key={track.tracking_id}>
                  <Heading>
                    {track.symbol} · {track.timeframe} · {track.portfolio_id}
                  </Heading>
                  <Row
                    name="Durum"
                    value={
                      !track.enabled
                        ? "Duraklatıldı"
                        : !track.worker_running
                          ? "PC işçisi kapalı"
                          : track.status === "waiting_data"
                            ? "Veri bekliyor"
                            : track.status === "error"
                              ? "İşçi hatası"
                              : "Son sorguda izliyordu"
                    }
                  />
                  <Label muted>
                    Son kontrol: {stamp(track.last_checked_ms)}
                  </Label>
                  <Label muted>
                    Durum sorgusu: {stamp(q.data?.checkedAt ?? null)}
                  </Label>
                  <Label>
                    {directionText(track.last_direction)} ·{" "}
                    {reasonText(track.last_reason)}
                  </Label>
                  <Button
                    title={track.enabled ? "Takibi durdur" : "Takibe devam et"}
                    secondary
                    disabled={!canWrite || busy || q.loading || !!q.error}
                    onPress={() =>
                      mutate(() =>
                        app.api.changeFollow(track.tracking_id, !track.enabled),
                      )
                    }
                  />
                  <Button
                    title="Son takip analizini aç"
                    variant="ghost"
                    onPress={() =>
                      router.push({
                        pathname: "/result",
                        params: { id: track.last_analysis_id },
                      })
                    }
                  />
                  {changesOpen ? (
                    changes.loading ? (
                      <Label muted>Koşul değişiklikleri yükleniyor…</Label>
                    ) : changes.error ? (
                      <Label>Değişiklik kaydı alınamadı: {changes.error}</Label>
                    ) : change ? (
                      <Label muted>
                        Son kaydedilen değişim: {stamp(change.created_at_ms)} ·{" "}
                        {directionText(String(change.details.direction))} ·{" "}
                        {reasonText(String(change.details.reason))}
                      </Label>
                    ) : (
                      <Label muted>
                        Yüklenen son 100 outbox kaydında bu takip için
                        değişiklik bulunamadı.
                      </Label>
                    )
                  ) : null}
                </Card>
              );
            })
          )}
          {rows.length > limit ? (
            <Button
              title="Daha fazla takip"
              secondary
              onPress={() => setLimit((v) => v + 20)}
            />
          ) : null}
          <Button
            title={
              startOpen ? "Yeni takip listesini kapat" : "Yeni takip başlat"
            }
            variant="ghost"
            disabled={!canWrite}
            onPress={() => setStartOpen((v) => !v)}
          />
          {startOpen ? (
            candidates.loading ? (
              <Loading />
            ) : candidates.error ? (
              <Failure message={candidates.error} retry={candidates.reload} />
            ) : !candidates.data?.length ? (
              <Empty text="Son analizlerde uygun kayıt yok. Önce analiz alın." />
            ) : (
              candidates.data.map((a) => (
                <Button
                  key={a.analysis_id}
                  title={
                    a.symbol +
                    " · " +
                    a.timeframe +
                    " · " +
                    a.risk_portfolio +
                    " takip et"
                  }
                  secondary
                  disabled={
                    busy ||
                    q.loading ||
                    !!q.error ||
                    q.data?.rows.some(
                      (t) =>
                        t.origin_analysis_id === a.analysis_id ||
                        (t.enabled &&
                          t.symbol === a.symbol &&
                          t.timeframe === a.timeframe &&
                          t.portfolio_id === a.risk_portfolio),
                    )
                  }
                  onPress={() => mutate(() => app.api.follow(a.analysis_id))}
                />
              ))
            )
          ) : null}
          <Button
            title={
              changesOpen
                ? "Koşul kayıtlarını yenile"
                : "Son koşul değişikliklerini yükle"
            }
            variant="ghost"
            disabled={changes.loading}
            onPress={() => {
              if (changesOpen) changes.reload();
              else setChangesOpen(true);
            }}
          />
          {message.scope === scope && message.text ? (
            <Label>{message.text}</Label>
          ) : null}
          <Label muted>
            PC işçisi ve özel ağ gerekir. Son sorgu çalışma garantisi değildir.
            Kayıtlar pending outbox’tır; Android push teslimi yoktur. Sanal emir
            açılmaz.
          </Label>
        </>
      )}
    </Page>
  );
}
