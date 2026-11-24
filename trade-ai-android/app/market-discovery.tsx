import React, { useState } from "react";
import { router } from "expo-router";
import { useApp } from "../src/state";
import { useResource } from "../src/resource";
import {
  opportunityPage,
  opportunityStale,
} from "../src/domain/opportunityView";
import { usePage } from "../src/usePage";
import type { components } from "../src/api/schema";
import { ScannerHealth, useUiClock } from "../src/ScannerHealth";
import { ScannerConfiguration } from "../src/ScannerConfiguration";
import { scannerReadiness } from "../src/domain/scannerReadiness";
import { userErrorText } from "../src/domain/presentation";
import {
  Page,
  Card,
  Heading,
  Label,
  Button,
  Choices,
  Loading,
  Failure,
  Row,
  Disclosure,
} from "../src/ui";
type M = components["schemas"];
const labels: Record<string, string> = {
  EARLY: "ERKEN · teyit bekleniyor",
  CONFIRMED: "TEYİTLİ · mevcut strateji koşulları sağlandı",
  INVALIDATED: "GEÇERSİZ · koşul kayboldu",
  EXPIRED: "SÜRESİ DOLDU",
  UNAVAILABLE: "VERİ KULLANILAMIYOR",
};
const time = (v: unknown) =>
  typeof v === "number" &&
  Number.isSafeInteger(v) &&
  v >= 0 &&
  v <= 253402300799999
    ? new Date(v).toISOString()
    : "Henüz yok";
export default function MarketDiscovery() {
  const app = useApp();
  const scope = [app.account, app.connectionKey, app.config.session].join("|");
  const page = usePage(scope);
  const [opportunityFilter, setOpportunityFilter] = useState("Hepsi");
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("dual-scanner-v1") &&
    app.sessionInfo.accounts.includes(app.account) &&
    app.sessionInfo.scopes.includes("read");
  const q = useResource(
    async () =>
      supported
        ? Promise.all([
            app.api.marketScanner(app.account),
            app.api.opportunities(app.account, page.offset),
          ])
        : null,
    [scope, supported, page.offset].join("|"),
  );
  const now = useUiClock(scope, q.loadedAt);
  const opportunities = opportunityPage(
    q.data?.[1].items ?? [],
    opportunityFilter,
    app.account,
  );
  const [reconnecting, setReconnecting] = useState(false),
    [connectionMessage, setConnectionMessage] = useState("");
  const readiness = scannerReadiness({
    mode: app.mode,
    gatewayVerified: app.gatewayVerified,
    phase: app.connectionPhase,
    errorCode: q.errorCode ?? app.connectionErrorCode,
    errorStatus: q.errorStatus,
    accounts: app.sessionInfo?.accounts,
    account: app.account,
    scopes: app.sessionInfo?.scopes,
    capabilities: app.sessionInfo?.capabilities,
    runtime: q.stale ? undefined : q.data?.[0].runtime,
  });
  async function reconnect() {
    if (reconnecting) return;
    setReconnecting(true);
    setConnectionMessage("");
    try {
      await app.reconnect();
      q.reload();
    } catch (e) {
      setConnectionMessage(userErrorText(e));
    } finally {
      setReconnecting(false);
    }
  }
  return (
    <Page mode={app.mode} connection={app} headerShown>
      <Heading>Favorilerim ve Akıllı Keşif</Heading>
      <Card>
        <ScannerHealth
          now={now}
          scope={scope}
          lastVerifiedAt={app.lastVerifiedAt}
          input={{
            mode: app.mode,
            gatewayVerified: app.gatewayVerified,
            phase: app.connectionPhase,
            errorCode: q.errorCode ?? app.connectionErrorCode,
            errorStatus: q.errorStatus,
            recovering: reconnecting || app.renewing,
            account: app.account,
            accounts: app.sessionInfo?.accounts,
            scopes: app.sessionInfo?.scopes,
            runtime: q.stale ? undefined : q.data?.[0].runtime,
            observedAt: q.data ? q.loadedAt : null,
            stale: q.stale,
            scanIntervalMs:
              typeof q.data?.[0].config.interval_seconds === "number"
                ? q.data[0].config.interval_seconds * 1000
                : undefined,
          }}
        />
        <Heading>Tarama izni ve hazırlık</Heading>
        <Label>{readiness.title}</Label>
        <Label>{readiness.detail}</Label>
        <Button
          title="Bağlantıyı yeniden doğrula"
          secondary
          disabled={reconnecting}
          onPress={() => void reconnect()}
        />
        <Button
          title="Bağlantı ayarlarını kontrol et"
          secondary
          onPress={() => router.push("/(tabs)/settings")}
        />
        {connectionMessage ? <Label>{connectionMessage}</Label> : null}
      </Card>
      <Choices
        values={app.sessionInfo?.accounts ?? [app.account]}
        value={app.account}
        onChange={(v) => app.setAccount(v as "AUTO" | "MANUAL")}
      />
      <Label>
        Yalnızca desteklenen BTC/ETH/SOL USDT spot pariteleri. EARLY
        bilgilendiricidir. Teyit, işlem izni değildir. Gerçek push kapalıdır.
      </Label>
      {!supported ? (
        <Card>
          <Label>
            Güncel Gateway, canlı bağlantı ve hesap okuma yetkisi gerekir. Demo
            veya eski Gateway için keşif sonucu üretilmez.
          </Label>
        </Card>
      ) : (
        <>
          <Button
            title="Durumu yenile"
            secondary
            disabled={q.loading}
            onPress={q.reload}
          />
          {q.loading ? (
            <Loading />
          ) : q.error ? (
            <Failure message={q.error} retry={q.reload} />
          ) : null}
          {q.data && !q.loading && !q.stale ? (
            <>
              <ScannerConfiguration
                now={now}
                key={scope + String(q.data[0].config.revision)}
                view={q.data[0]}
                reload={q.reload}
              />
              <Card>
                <Heading>Worker ve kaynak durumu</Heading>
                <Row
                  name="Worker"
                  value={
                    q.data[0].runtime.worker_active === true
                      ? "Aktif lease · heartbeat aşağıda"
                      : "Aktif worker doğrulanmadı"
                  }
                />
                <Row
                  name="Hesap tarama isteği"
                  value={q.data[0].config.enabled === true ? "Etkin" : "Pasif"}
                />
                <Row
                  name="Favori kapsamı"
                  value={
                    Array.isArray(q.data[0].config.favorites) &&
                    q.data[0].config.favorites.length
                      ? String(q.data[0].config.favorites.length) +
                        " parite · izin varsa taranır"
                      : "Favori seçilmemiş"
                  }
                />
                <Row
                  name="Piyasa keşfi"
                  value={
                    q.data[0].config.discovery === true
                      ? "Kayıtlı kapsam açık · veri/worker gerekir"
                      : "Kapalı"
                  }
                />
                <Row
                  name="Kayıtlı kontrol aralığı"
                  value={String(q.data[0].config.interval_seconds) + " saniye"}
                />
                <Row
                  name="Planlanan sonraki kontrol (UTC)"
                  value={
                    q.data[0].config.enabled === true
                      ? typeof q.data[0].runtime.next_due_ms === "number" &&
                        q.data[0].runtime.next_due_ms > 0
                        ? time(q.data[0].runtime.next_due_ms)
                        : "Henüz planlanmadı"
                      : "Hesap pasif · plan çalışmaz"
                  }
                />
                <Label muted>
                  Planlanan zaman bir çalışma garantisi değildir; durmuş worker
                  durumunda geçmişte kalabilir. Ayrı process başlat/durdur API
                  desteği desteklenmiyor.
                </Label>
                <Disclosure title="Worker ve sağlayıcı ayrıntıları">
                  <Row
                    name="Heartbeat (UTC)"
                    value={time(q.data[0].runtime.heartbeat_ms)}
                  />
                  <Row
                    name="Son deneme (UTC)"
                    value={time(q.data[0].runtime.last_attempt_ms)}
                  />
                  <Row
                    name="Son kaynak başarısı (UTC)"
                    value={time(q.data[0].runtime.last_success_ms)}
                  />
                  <Row
                    name="Son keşif (UTC)"
                    value={time(q.data[0].runtime.last_discovery_ms)}
                  />
                  <Row
                    name="Kaynak"
                    value={String(q.data[0].runtime.provider_status)}
                  />
                  <Row
                    name="Uygun / taranan / bekleyen"
                    value={[
                      q.data[0].runtime.eligible,
                      q.data[0].runtime.screened,
                      q.data[0].runtime.backlog,
                    ]
                      .map(String)
                      .join(" / ")}
                  />
                  <Label muted>
                    Gateway erişimi worker durumunun çalıştığını kanıtlamaz.
                    Uygulamayı açmak worker başlatmaz. Likidite/spread filtresi
                    doğrulanmadığından uygulanmıyor.
                  </Label>
                </Disclosure>
              </Card>
              <Heading>Fırsat geçmişi</Heading>
              <Choices
                values={[
                  "Hepsi",
                  "Erken",
                  "Teyitli",
                  "Geçersiz / süresi dolmuş",
                ]}
                value={opportunityFilter}
                onChange={setOpportunityFilter}
              />
              <Label muted>
                Filtre yalnız bu sayfanın gerçek kayıtlarına uygulanır. Aynı
                fırsat kimliği bir kez gösterilir; yeni kayıt eski analizi
                değiştirmez.
              </Label>
              {!q.data[1].items.length ? (
                <Label>
                  Bu hesapta kayıtlı fırsat yok. Koşullar oluşmadığında boş
                  kalabilir.
                </Label>
              ) : opportunities.length ? (
                opportunities.map((o) => (
                  <Opportunity key={o.opportunity_id} value={o} now={now} />
                ))
              ) : (
                <Label>
                  Bu sayfada filtreye uygun kayıt yok. Diğer sayfaları kontrol
                  edebilirsiniz.
                </Label>
              )}
              <Button
                title="Önceki sayfa"
                secondary
                disabled={page.offset === 0}
                onPress={page.previous}
              />
              <Button
                title="Sonraki sayfa"
                secondary
                disabled={q.data[1].next_offset === null}
                onPress={page.next}
              />
            </>
          ) : null}
        </>
      )}
    </Page>
  );
}
function Opportunity({
  value: o,
  now,
}: {
  value: M["OpportunityRecord"];
  now: number;
}) {
  const app = useApp();
  const [expanded, setExpanded] = useState(false);
  const q = useResource(
    async () =>
      expanded ? app.api.opportunity(app.account, o.opportunity_id) : null,
    [
      app.account,
      app.connectionKey,
      app.config.session,
      o.opportunity_id,
      expanded,
    ].join("|"),
  );
  return (
    <Card>
      <Heading>
        {o.symbol} · {labels[o.state]}
      </Heading>
      <Label>
        {o.source} / {o.timeframe} · {o.modes.join(" + ")}
      </Label>
      <Label>İlk bilinen (UTC): {time(o.first_known_ms)}</Label>
      <Label>Son kaynak (UTC): {time(o.last_source_ms)}</Label>
      <Label>Geçerlilik sonu (UTC): {time(o.expires_at_ms)}</Label>
      {opportunityStale(o, now) || q.stale ? (
        <Label>
          Eski/kullanılamayan kayıt · güncel fırsat gibi yorumlanmamalı.
        </Label>
      ) : null}
      <Label>Neden: {o.reason}</Label>
      <Label>
        Eksik koşullar:{" "}
        {o.missing.join(", ") ||
          "Kayıtlı eksik koşul yok · işlem yetkisi verilmez"}
      </Label>
      <Button
        title={expanded ? "Kanıtı kapat" : "Kayıtlı kanıt ve olaylar"}
        secondary
        onPress={() => setExpanded(!expanded)}
      />
      {expanded ? (
        q.loading ? (
          <Loading />
        ) : q.error ? (
          <Failure message={q.error} retry={q.reload} />
        ) : q.data ? (
          <>
            <Label>{JSON.stringify(q.data.opportunity.evidence)}</Label>
            {q.data.events.map((e, i) => (
              <Label key={i}>
                {time(e.recorded_at_ms)} · {String(e.state)} ·{" "}
                {String(e.reason)}
              </Label>
            ))}
          </>
        ) : null
      ) : null}
      <Button
        title="Kaydedilmiş analizi aç"
        secondary
        onPress={() =>
          router.push({
            pathname: "/detail",
            params: { id: o.last_analysis_id },
          })
        }
      />
    </Card>
  );
}
