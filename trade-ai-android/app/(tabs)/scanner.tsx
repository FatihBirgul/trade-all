import { View } from "react-native";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { router } from "expo-router";
import { ScannerJournal } from "../../src/api/scannerJournal";
import { nativeIntentStorage } from "../../src/api/nativeIntent";
import { ApiError } from "../../src/api/client";
import { useApp } from "../../src/state";
import { useResource } from "../../src/resource";
import { usePage } from "../../src/usePage";
import { uniqueRecords } from "../../src/domain/records";
import { symbols, timeframes, lastScanText } from "../../src/domain/safety";
import {
  reasonText,
  userErrorText,
  scannerJobText,
} from "../../src/domain/presentation";
import type { components } from "../../src/api/schema";
import {
  Button,
  Card,
  Choices,
  Failure,
  ScreenHeader,
  Heading,
  Label,
  Loading,
  Page,
  Row,
  Disclosure,
} from "../../src/ui";
const scanTimeframes = timeframes.filter((t) => t !== "1m");
type ScanTimeframe = (typeof scanTimeframes)[number];
type Watch = components["schemas"]["WatchResponse"];
function ScannerContent() {
  const app = useApp();
  const [symbol, setSymbol] = useState<(typeof symbols)[number]>("BTCUSDT");
  const [tf, setTf] = useState<ScanTimeframe>("1H");
  const [jobLimit, setJobLimit] = useState(5);
  const [busy, setBusy] = useState(false);
  const actionLock = useRef(false);
  const [message, setMessage] = useState("");
  const [demoWatches, setDemoWatches] = useState<Watch[]>([
    {
      watch_id: "BTCUSDT:1H",
      symbol: "BTCUSDT",
      timeframe: "1H",
      enabled: true,
      auto_paper: false,
    },
  ]);
  const scope = [app.mode, app.connectionKey, app.config.session].join("|");
  const currentScope = useRef(scope);
  useEffect(() => {
    currentScope.current = scope;
  }, [scope]);
  const page = usePage(scope);
  const journal = useMemo(
    () =>
      new ScannerJournal(
        nativeIntentStorage,
        [app.config.origin, app.sessionInfo?.device_id, "AUTO"].join("|"),
      ),
    [app.config.origin, app.sessionInfo?.device_id],
  );
  const [pendingRevision, setPendingRevision] = useState(0);
  const pending = useResource(
    async () => (app.mode === "live" ? journal.pending() : null),
    [
      scope,
      pendingRevision,
      app.sessionInfo?.device_id,
      app.gatewayVerified,
    ].join("|"),
  );
  async function recover() {
    if (busy || app.mode !== "live" || !app.gatewayVerified) return;
    setBusy(true);
    const attempted = scope;
    try {
      const result = await journal.reconcile(app.api);
      if (currentScope.current === attempted) {
        setMessage(result.message);
        pending.reload();
        q.reload();
      }
    } catch (error) {
      if (currentScope.current === attempted) setMessage(userErrorText(error));
    } finally {
      setBusy(false);
    }
  }
  const q = useResource(
    async () => {
      if (app.mode === "demo")
        return {
          checkedAt: 0,
          running: false,
          paused: app.paused,
          last: app.lastTick,
          watches: demoWatches,
          error: null as string | null,
          jobs: [] as components["schemas"]["ScannerJob"][],
          interval: 60,
          maximum: 2,
        };
      const [s, watches, jobs] = await Promise.all([
        app.api.scanner(),
        app.api.watches(),
        app.api.jobs(page.offset),
      ]);
      return {
        checkedAt: Date.now(),
        running: !!s.lease_id && s.lease_until_ms > Date.now(),
        paused: s.paused,
        last: s.last_tick_ms,
        watches,
        error: s.last_error,
        jobs,
        interval: s.interval_seconds,
        maximum: s.max_analyses_per_tick,
      };
    },
    [scope, app.paused, app.lastTick, demoWatches, page.offset]
      .map((v) => (typeof v === "object" ? JSON.stringify(v) : v))
      .join("|"),
  );
  const [profileId, setProfileId] = useState<string | null>(null);
  const supportsProfiles =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("profile-scanner-v1") &&
    !!app.sessionInfo.accounts.includes("AUTO");
  const profileOptions = useResource(
    async () => (supportsProfiles ? app.api.profiles("AUTO") : []),
    scope + "|profile-options|" + supportsProfiles,
  );
  const selectedProfile = profileOptions.data?.find(
    (p) => p.profile_id === profileId,
  );
  const profileReady =
    !profileId ||
    (supportsProfiles &&
      !profileOptions.loading &&
      !profileOptions.error &&
      selectedProfile?.selection.setup_timeframe === tf);
  const canWrite =
    app.mode === "demo" ||
    (app.gatewayVerified &&
      !q.loading &&
      !q.stale &&
      !q.error &&
      !!q.data &&
      app.sessionInfo?.scopes.includes("scanner:write") === true &&
      app.sessionInfo.accounts.includes("AUTO"));
  async function action(
    kind: "pause" | "tick" | "watch",
    watch?: Watch,
    eventTime?: number,
  ) {
    if (
      busy ||
      actionLock.current ||
      !canWrite ||
      !q.data ||
      (kind === "watch" && !watch && !profileReady)
    )
      return;
    actionLock.current = true;
    setBusy(true);
    setMessage("");
    const attemptedScope = scope;
    try {
      if (app.mode === "demo") {
        if (kind === "pause") app.setPaused(!app.paused);
        else if (kind === "watch") {
          const next: Watch = watch
            ? { ...watch, enabled: !watch.enabled, auto_paper: false }
            : {
                watch_id: symbol + ":" + tf,
                symbol,
                timeframe: tf,
                enabled: true,
                auto_paper: false,
              };
          setDemoWatches((rows) =>
            uniqueRecords([...rows, next], (w) => w.watch_id),
          );
        } else if (!app.paused) {
          if (eventTime === undefined)
            throw new Error("Tarama zamanı alınamadı.");
          app.setLastTick(eventTime);
          setMessage(
            "Demo kontrolü tamamlandı. Piyasa verisi veya emir üretilmedi.",
          );
        }
      } else {
        if (kind === "pause") {
          await app.api.pause(!q.data.paused);
          if (currentScope.current === attemptedScope)
            setMessage(
              "Tarayıcı duraklatma tercihi kaydedildi. Bu yanıt PC işçisinin çalıştığını doğrulamaz.",
            );
        } else if (kind === "watch")
          await app.api.watch(
            watch
              ? {
                  ...(watch.profile_id ? { profile_id: watch.profile_id } : {}),
                  symbol: watch.symbol,
                  timeframe: watch.timeframe,
                  enabled: !watch.enabled,
                  auto_paper: false,
                }
              : {
                  ...(profileId ? { profile_id: profileId } : {}),
                  symbol,
                  timeframe: tf,
                  enabled: true,
                  auto_paper: false,
                },
          );
        else {
          const result = await journal.execute(app.api);
          if (currentScope.current !== attemptedScope) return;
          setMessage(
            {
              paused: "Tarayıcı duraklatılmış",
              busy: "Tarayıcı meşgul",
              completed: "Tarama tamamlandı",
              blocked: "Tarama engellendi",
            }[result.status] +
              (result.reason ? " · " + reasonText(result.reason) : ""),
          );
        }
        if (currentScope.current === attemptedScope) q.reload();
      }
    } catch (e) {
      if (currentScope.current !== attemptedScope) return;
      if (kind === "tick" && e instanceof ApiError && e.uncertain) {
        try {
          const result = await journal.reconcile(app.api);
          if (currentScope.current === attemptedScope) {
            setMessage(result.message);
            q.reload();
          }
        } catch {
          if (currentScope.current === attemptedScope)
            setMessage(
              "Tarama yanıtı alınamadı. Yeni tarama gönderilmedi; bekleyen taramayı kontrol edin.",
            );
        }
      } else setMessage(userErrorText(e));
    } finally {
      actionLock.current = false;
      setPendingRevision((value) => value + 1);
      setBusy(false);
    }
  }
  const exists = q.data?.watches.some(
    (w) => w.symbol === symbol && w.timeframe === tf,
  );
  const cooling =
    app.mode === "live" &&
    q.data?.last != null &&
    q.data.checkedAt < q.data.last + q.data.interval * 1000;
  return (
    <Page mode={app.mode} connection={app}>
      <Button
        title="Favorilerim ve Akıllı Keşif"
        onPress={() => router.push("/market-discovery")}
      />
      <ScreenHeader title="Piyasa tarayıcı" badge="PRO / TARAYICI" />
      {app.mode === "demo" ? (
        <Label muted>
          Yerel DEMO simülasyonu · izlemeler örnektir. PC/Gateway scanner durumu
          sorgulanmaz; aşağıdaki kontroller yalnız telefondaki örneği
          değiştirir.
        </Label>
      ) : null}
      {pending.error ? <Label>{pending.error}</Label> : null}
      {pending.data ? (
        <Card>
          <Label>Bekleyen tarama kaydı var. Yeni tick gönderilmez.</Label>
          <Button
            title="Bekleyen taramayı kontrol et"
            secondary
            disabled={busy || !app.gatewayVerified}
            onPress={recover}
          />
        </Card>
      ) : null}
      {app.mode === "live" && !canWrite ? (
        <Label muted>
          Tarayıcı salt okunur. Kontroller için bilgisayardan ayrı scanner
          yetkisi verilmelidir.
        </Label>
      ) : null}
      <Button
        title="Tarayıcıyı yenile"
        secondary
        disabled={busy}
        onPress={q.reload}
      />
      {q.loading ? (
        <Loading />
      ) : q.error ? (
        <Failure
          message={"Bağlantı yok · sunucu durumu doğrulanamadı. " + q.error}
          retry={q.reload}
        />
      ) : q.data ? (
        <>
          <Card>
            <Row
              name="Durum"
              value={
                app.mode === "demo"
                  ? q.data.paused
                    ? "DEMO · yerel örnek duraklatıldı"
                    : "DEMO · yerel örnek açık"
                  : q.data.paused
                    ? "Son sorguda duraklatıldı"
                    : q.data.running
                      ? "Son sorguda sunucuda iş göründü"
                      : "İzleme açık · son sorguda aktif iş yok"
              }
            />
            <Row
              name={app.mode === "demo" ? "Yerel kontrol" : "Son tarama"}
              value={
                app.mode === "demo" && !q.data.last
                  ? "Yerel kontrol yapılmadı"
                  : lastScanText(q.data.last)
              }
            />
            {app.mode === "live" ? (
              <Label muted>
                Son başarılı sorgu:{" "}
                {new Date(q.data.checkedAt).toLocaleString("tr-TR")}. Devam
                tercihi, worker’ın çalıştığı anlamına gelmez.
              </Label>
            ) : null}
            <Label muted>
              En çok 10 kayıt, kontrolde en çok {q.data.maximum} analiz. Kontrol
              aralığı {q.data.interval} saniye. AUTO emir oluşturma kapalı.
              Mobil uygulama arka planda tarama zamanlamaz.
            </Label>
            {q.data.error ? <Label>{reasonText(q.data.error)}</Label> : null}
            <Button
              title={
                app.mode === "demo"
                  ? q.data.paused
                    ? "DEMO örneğini sürdür"
                    : "DEMO örneğini duraklat"
                  : q.data.paused
                    ? "Devam ettir"
                    : "Duraklat"
              }
              disabled={busy || !canWrite}
              onPress={() => action("pause")}
            />
            <Button
              title={
                app.mode === "demo" ? "Yerel kontrolü dene" : "Bir kez tara"
              }
              secondary
              disabled={
                busy ||
                !canWrite ||
                q.data.paused ||
                cooling ||
                pending.loading ||
                !!pending.data ||
                !!pending.error
              }
              onPress={() => action("tick", undefined, Date.now())}
            />
            {cooling ? (
              <Label muted>
                Tarama aralığı dolunca Yenile ile kontrol edin.
              </Label>
            ) : null}
          </Card>
          <Card>
            <Heading>
              {app.mode === "demo" ? "Örnek izleme listesi" : "İzleme listesi"}
            </Heading>
            {!q.data.watches.length ? (
              <Label muted>Sunucu boş izleme listesi döndürdü.</Label>
            ) : null}
            {q.data.watches.map((w) => (
              <View
                key={w.watch_id}
                style={{
                  flexDirection: "row",
                  flexWrap: "wrap",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 6,
                }}
              >
                <Label>
                  {w.symbol} · {w.timeframe} ·{" "}
                  {app.mode === "demo"
                    ? w.enabled
                      ? "Örnek açık"
                      : "Örnek kapalı"
                    : w.enabled
                      ? "Açık"
                      : "Kapalı"}
                </Label>
                {w.profile_id ? (
                  <Label muted>
                    Değişmez profil: {w.profile_id.slice(0, 12)}
                  </Label>
                ) : null}
                <Button
                  title={w.enabled ? "Durdur" : "Devam"}
                  accessibilityLabel={
                    (w.enabled ? "İzlemeyi kapat · " : "İzlemeyi aç · ") +
                    w.watch_id
                  }
                  variant="ghost"
                  disabled={busy || !canWrite}
                  onPress={() => action("watch", w)}
                />
              </View>
            ))}
            <Disclosure title="Yeni izleme kaydı">
              <Choices values={symbols} value={symbol} onChange={setSymbol} />
              <Choices values={scanTimeframes} value={tf} onChange={setTf} />
              {supportsProfiles ? (
                <>
                  <Label>Profil filtresi · son 20 kayıtlı revizyon</Label>
                  {profileOptions.error ? (
                    <Label>{profileOptions.error}</Label>
                  ) : null}
                  <Button
                    title="Profilsiz tarama"
                    disabled={busy}
                    onPress={() => setProfileId(null)}
                  />
                  {profileOptions.data?.map((p) => (
                    <Button
                      key={p.profile_id}
                      title={
                        (profileId === p.profile_id
                          ? "Seçili · "
                          : "Profil · ") +
                        p.profile_id.slice(0, 8) +
                        " · v" +
                        p.revision +
                        " · " +
                        p.selection.setup_timeframe
                      }
                      disabled={busy || !!profileOptions.error}
                      onPress={() => setProfileId(p.profile_id)}
                    />
                  ))}
                  {!profileReady ? (
                    <Label>
                      Profilin kurulum zaman dilimi seçili zaman dilimiyle
                      eşleşmeli; veri okunana kadar kayıt yazılmaz.
                    </Label>
                  ) : null}
                  <Label muted>
                    Profil seçimi tarayıcıyı başlatmaz ve otomatik emir izni
                    vermez.
                  </Label>
                </>
              ) : null}
              <Button
                title={
                  exists
                    ? "Kayıt mevcut · yukarıdan yönet"
                    : "İzlemeye ekle · " + tf
                }
                secondary
                disabled={
                  busy ||
                  !canWrite ||
                  !profileReady ||
                  exists ||
                  q.data.watches.length >= 10
                }
                onPress={() => action("watch")}
              />
            </Disclosure>
          </Card>
          <Card>
            <Heading>Son tarama işleri</Heading>
            {uniqueRecords(q.data.jobs, (j) => j.job_id)
              .slice(0, jobLimit)
              .map((j) => (
                <React.Fragment key={j.job_id}>
                  <Label>
                    {j.symbol} · {j.timeframe} · {scannerJobText(j.status)}
                    {j.reason ? " · " + reasonText(j.reason) : ""}
                  </Label>
                  {j.analysis_id ? (
                    <Button
                      title="Tarama analizini aç"
                      secondary
                      onPress={() =>
                        router.push({
                          pathname: "/detail",
                          params: { id: j.analysis_id! },
                        })
                      }
                    />
                  ) : null}
                </React.Fragment>
              ))}
            {q.data.jobs.length > jobLimit ? (
              <Button
                title="Bu sayfanın tüm işlerini göster"
                variant="ghost"
                onPress={() => setJobLimit(20)}
              />
            ) : null}
            {!q.data.jobs.length ? (
              <Label muted>
                {app.mode === "demo"
                  ? "DEMO’da sunucu taraması yapılmaz; gerçek tarama işleri sorgulanmadı."
                  : "Sunucu bu sayfa için boş tarama işi listesi döndürdü."}
              </Label>
            ) : null}
            <Button
              title="Önceki taramalar"
              secondary
              disabled={!page.offset}
              onPress={page.previous}
            />
            <Button
              title="Sonraki taramalar"
              secondary
              disabled={q.data.jobs.length < 20}
              onPress={page.next}
            />
          </Card>
        </>
      ) : null}
      {message ? (
        <Card>
          <Label>{message}</Label>
        </Card>
      ) : null}
    </Page>
  );
}

export default function Scanner() {
  const app = useApp();
  if (app.uiMode === "basic")
    return (
      <Page mode={app.mode} connection={app}>
        <Heading>Pro özelliği</Heading>
        <Label>
          Bu ekranın gelişmiş kontrolleri için Ayarlar’dan Pro modunu
          etkinleştirin. Analiz kararı değişmez.
        </Label>
        <Button title="Ayarları aç" onPress={() => router.push("/settings")} />
      </Page>
    );
  return <ScannerContent />;
}
