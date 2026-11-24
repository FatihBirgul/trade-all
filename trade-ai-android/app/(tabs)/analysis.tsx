import React, { useEffect, useRef, useState } from "react";
import { useLocalSearchParams, router } from "expo-router";
import * as Crypto from "expo-crypto";
import { useResource } from "../../src/resource";
import { useApp } from "../../src/state";
import { ScreenHeader, Button, Card, Label, Page, Choices } from "../../src/ui";
import { symbols, timeframes, type Timeframe } from "../../src/domain/safety";
import { demoAnalysis } from "../../src/demo";
import { ApiError } from "../../src/api/client";
import { userErrorText } from "../../src/domain/presentation";
export default function AnalysisScreen() {
  const app = useApp();
  const params = useLocalSearchParams<{
    profileId?: string;
    symbol?: string;
    requestId?: string;
    timeframe?: string;
    mtf?: string;
    previous?: string;
  }>();
  const routeSymbol = symbols.find((s) => s === params.symbol) || "BTCUSDT";
  const routeId = params.requestId || "tab";
  const [selection, setSelection] = useState<{
    routeId: string;
    symbol: (typeof symbols)[number];
  } | null>(null);
  const symbol =
    selection?.routeId === routeId ? selection.symbol : routeSymbol;
  const [frames, setFrames] = useState<{
    routeId: string;
    tf: Timeframe;
    mtf: Timeframe[];
  } | null>(null);
  const tf =
    frames?.routeId === routeId
      ? frames.tf
      : timeframes.find((t) => t === params.timeframe) || "1H";
  const mtf: Timeframe[] =
    frames?.routeId === routeId
      ? frames.mtf
      : params.mtf
        ? timeframes.filter((t) => params.mtf?.split(",").includes(t))
        : ["15m", "4H"];
  const setTf = (value: Timeframe) => setFrames({ routeId, tf: value, mtf });
  const setMtf = (change: (old: Timeframe[]) => Timeframe[]) =>
    setFrames({ routeId, tf, mtf: change(mtf) });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const pending = useRef<{
    id: string;
    symbol: typeof symbol;
    tf: Timeframe;
    mtf: Timeframe[];
    account: typeof app.account;
    profileId?: string;
  } | null>(null);
  const modeRef = useRef(app.mode);
  const scopeRef = useRef(app.connectionKey);
  const markets = useResource(
    async () => (app.mode === "live" ? app.api.markets() : null),
    [app.mode, app.connectionKey, app.config.session].join("|"),
  );
  useEffect(() => {
    modeRef.current = app.mode;
    scopeRef.current = app.connectionKey;
  }, [app.mode, app.connectionKey]);
  const profileSupported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("strategy-profiles-v1");
  const profile = useResource(
    async () =>
      params.profileId && profileSupported
        ? app.api.profile(app.account, params.profileId)
        : null,
    [
      app.connectionKey,
      app.config.session,
      app.account,
      params.profileId,
      profileSupported,
    ].join("|"),
  );
  async function analyze() {
    if (
      busy ||
      (params.profileId &&
        (!profile.data || profile.error || !profileSupported))
    )
      return;
    setBusy(true);
    setError("");
    const mode = app.mode;
    const scope = app.connectionKey;
    const p = pending.current || {
      id: Crypto.randomUUID(),
      symbol,
      tf,
      mtf: mtf.filter((t) => t !== tf),
      account: app.account,
      profileId: params.profileId,
    };
    pending.current = p;
    try {
      const result =
        mode === "demo"
          ? demoAnalysis(p.symbol, p.tf, p.account, p.id)
          : await app.api.analyze({
              ...(p.profileId ? { profile_id: p.profileId } : {}),
              symbol: p.symbol,
              market: "crypto_spot",
              timeframe: p.tf,
              timeframes: p.mtf,
              risk_portfolio: p.account,
              auto_paper: false,
              data_mode: "live",
              idempotency_key: p.id,
            });
      if (modeRef.current !== mode || scopeRef.current !== scope) return;
      if (result.data_mode !== (mode === "demo" ? "fixture" : "live"))
        throw new Error("Veri modu uyuşmazlığı.");
      app.addAnalysis(result);
      pending.current = null;
      setUncertain(false);
      router.push({
        pathname: "/result",
        params: {
          id: result.analysis_id,
          ...(params.previous ? { compare: params.previous } : {}),
        },
      });
    } catch (e) {
      if (modeRef.current !== mode || scopeRef.current !== scope) return;
      const unknown = e instanceof ApiError && e.uncertain;
      setUncertain(unknown);
      if (!unknown) pending.current = null;
      setError(userErrorText(e, "Analiz tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Page mode={app.mode} connection={app}>
      <ScreenHeader title="Yeni analiz" badge="PİYASA ANALİZİ" />
      <Label muted>Teknik görünüm, çoklu zaman dilimi ve risk kontrolü.</Label>
      {markets.error ? <Label>{markets.error}</Label> : null}
      <Button
        title="Strateji profillerini yönet"
        secondary
        disabled={busy || uncertain}
        onPress={() => router.push("/strategy-profiles")}
      />
      <Label>Analiz hesabı: {app.account} · yalnız sanal</Label>
      {!params.profileId ? (
        <Label muted>Profil: varsayılan V2 strateji seçimi</Label>
      ) : null}
      {params.profileId ? (
        <Card>
          <Label>Seçili değişmez profil: {params.profileId.slice(0, 12)}</Label>
          <Label muted>
            Bu profil yalnız mevcut analizi daraltır. Zaman dilimleri profil
            rolleriyle eşleşmelidir.
          </Label>
          {profile.error ? <Label>{profile.error}</Label> : null}
          <Button
            title="Profilsiz analize dön"
            disabled={busy || uncertain}
            onPress={() => router.setParams({ profileId: undefined })}
          />
        </Card>
      ) : null}
      <Card>
        <Label>Piyasa · Spot</Label>
        <Choices
          values={symbols}
          value={symbol}
          onChange={(next) => setSelection({ routeId, symbol: next })}
        />
        <Label>Ana zaman dilimi</Label>
        <Choices values={timeframes} value={tf} onChange={setTf} />
        {app.uiMode === "pro" ? (
          <>
            <Label>MTF · Ek zaman dilimleri</Label>
            <Choices
              values={timeframes.filter((t) => t !== tf)}
              value={mtf.filter((t) => t !== tf)}
              onChange={(v) =>
                setMtf((old) =>
                  old.includes(v)
                    ? old.filter((t) => t !== v)
                    : [...old.filter((t) => t !== tf), v].slice(0, 5),
                )
              }
            />
            <Label>Risk hesabı</Label>
            <Choices
              values={["AUTO", "MANUAL"] as const}
              value={app.account}
              onChange={app.setAccount}
              disabledValues={
                app.mode === "live"
                  ? (["AUTO", "MANUAL"] as const).filter(
                      (v) => !app.sessionInfo?.accounts.includes(v),
                    )
                  : []
              }
            />
          </>
        ) : (
          <Label muted>
            Ek zaman dilimi ve risk hesabı ayarları Pro modundadır. Seçili
            analiz ayarları mod değişince korunur.
          </Label>
        )}
        <Label muted>
          Analiz otomatik emir oluşturmaz. Eksik kritik veride WAIT gösterilir.
        </Label>
        {error ? <Label>{error}</Label> : null}
        {uncertain ? (
          <Label>
            Tekrar deneme ilk isteğin aynı anahtarını ve aynı içeriğini
            kullanır.
          </Label>
        ) : null}
        <Button
          title={
            busy
              ? "Analiz hazırlanıyor…"
              : uncertain
                ? "Aynı isteği yeniden dene"
                : "Analizi başlat"
          }
          disabled={
            busy ||
            (!!params.profileId &&
              (!profile.data || !!profile.error || !profileSupported)) ||
            (app.mode === "live" &&
              (!app.gatewayVerified ||
                !app.sessionInfo?.scopes.includes("analyze") ||
                !markets.data ||
                !markets.data.items.some(
                  (m) => m.symbol === symbol && m.availability === "configured",
                )))
          }
          onPress={analyze}
        />
      </Card>
    </Page>
  );
}
