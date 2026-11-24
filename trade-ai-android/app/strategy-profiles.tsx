import React, { useRef, useState } from "react";
import * as Crypto from "expo-crypto";
import { router } from "expo-router";
import { useApp } from "../src/state";
import { useResource } from "../src/resource";
import { ApiError } from "../src/api/client";
import type { components } from "../src/api/schema";
import { object } from "../src/analysisView";
import { Button, Card, Choices, Heading, Label, Page, Row } from "../src/ui";
import { userErrorText } from "../src/domain/presentation";
import { timeframes } from "../src/domain/safety";
type Selection = components["schemas"]["ProfileSelection"];
type Record = components["schemas"]["ProfileRecord"];
const initial: Selection = {
  strategy_ids: [
    "trend_momentum_v2",
    "range_mean_reversion_v2",
    "confirmed_breakout_v2",
    "failed_breakout_v2",
  ],
  required_methods: ["roc12"],
  allowed_regimes: ["trend", "range", "breakout", "reversal"],
  bias_timeframe: "1H",
  setup_timeframe: "1H",
  trigger_timeframe: "1H",
  minimum_confirmations: 2,
  analysis_every_bars: 10,
};
export default function Profiles() {
  const app = useApp();
  const scope = [
    app.mode,
    app.connectionKey,
    app.config.session,
    app.account,
  ].join("|");
  const available =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("strategy-profiles-v1") &&
    !!app.sessionInfo.accounts.includes(app.account);
  return (
    <Page>
      <Heading>Strateji profilleri</Heading>
      <Label>
        Hesap: {app.account}. Profil yalnız mevcut stratejiyi daraltır; WAIT,
        risk limitleri ve emir yetkileri korunur.
      </Label>
      {available ? (
        <ProfileEditor key={scope} />
      ) : (
        <Card>
          <Label>
            Bu özellik doğrulanmış CANLI bağlantı, hesap yetkisi ve güncel
            Backend/Gateway gerektirir. DEMO profil kaydetmez.
          </Label>
        </Card>
      )}
    </Page>
  );
}
function ProfileEditor() {
  const app = useApp();
  const [offset, setOffset] = useState(0);
  const list = useResource(
    () => app.api.profiles(app.account, offset),
    "profiles:" + offset,
  );
  const catalogue = useResource(
    () => app.api.strategyCapabilities(),
    "catalogue",
  );
  const [selection, setSelection] = useState<Selection>(initial);
  const [parent, setParent] = useState<Record | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [uncertain, setUncertain] = useState(false);
  const pending = useRef<{
    body: components["schemas"]["ProfileWrite"];
    parent?: string;
  } | null>(null);
  const writable = !!app.sessionInfo?.scopes.includes("profiles:write");
  const caps = object(catalogue.data);
  const names = (key: string, id: string) =>
    Array.isArray(caps[key])
      ? (caps[key] as unknown[])
          .map(object)
          .map((x) => x[id])
          .filter((v): v is string => typeof v === "string" && v.length < 100)
          .slice(0, 16)
      : [];
  const toggle = (
    key: "strategy_ids" | "required_methods" | "allowed_regimes",
    value: string,
  ) =>
    setSelection((old) => ({
      ...old,
      [key]: (old[key] || []).includes(value)
        ? (old[key] || []).filter((x) => x !== value)
        : [...(old[key] || []), value],
    }));
  async function save() {
    if (busy || !writable) return;
    setBusy(true);
    setError("");
    const command = pending.current || {
      body: { idempotency_key: Crypto.randomUUID(), selection },
      parent: parent?.profile_id,
    };
    pending.current = command;
    try {
      await app.api.saveProfile(app.account, command.body, command.parent);
      pending.current = null;
      setUncertain(false);
      setParent(null);
      setSelection(initial);
      setOffset(0);
      list.reload();
    } catch (e) {
      const unknown = e instanceof ApiError && e.uncertain;
      setUncertain(unknown);
      if (!unknown) pending.current = null;
      setError(userErrorText(e));
    } finally {
      setBusy(false);
    }
  }
  const locked = busy || uncertain;
  return (
    <>
      <Card>
        <Heading>Kayıtlı sürümler</Heading>
        {list.loading ? <Label>Yükleniyor…</Label> : null}
        {list.error ? <Label>{list.error}</Label> : null}
        {!list.loading && !list.data?.length ? (
          <Label>Bu sayfada profil yok.</Label>
        ) : null}
        {list.data?.map((p) => (
          <Card key={p.profile_id}>
            <Row name="Sürüm" value={String(p.revision)} />
            <Label muted>{p.selection.strategy_ids?.join(" · ")}</Label>
            <Label muted>
              {p.profile_id.slice(0, 12)} ·{" "}
              {new Date(p.created_at_ms).toLocaleString("tr-TR")}
            </Label>
            <Button
              title="Bu profille analiz al"
              disabled={locked || !!list.error}
              onPress={() =>
                router.push({
                  pathname: "/(tabs)/analysis",
                  params: {
                    profileId: p.profile_id,
                    timeframe: p.selection.setup_timeframe,
                    mtf: [
                      ...new Set([
                        p.selection.bias_timeframe,
                        p.selection.trigger_timeframe,
                      ]),
                    ].join(","),
                    requestId: Crypto.randomUUID(),
                  },
                })
              }
            />
            {writable ? (
              <Button
                title="Yeni revizyon hazırla"
                disabled={locked || !!list.error}
                onPress={() => {
                  setParent(p);
                  setSelection(p.selection);
                  setError("");
                }}
              />
            ) : null}
          </Card>
        ))}
        <Button
          title="Yenile"
          disabled={busy || list.loading}
          onPress={list.reload}
        />
        <Button
          title="Önceki sayfa"
          disabled={offset === 0 || locked}
          onPress={() => setOffset(Math.max(0, offset - 20))}
        />
        <Button
          title="Sonraki sayfa"
          disabled={locked || list.loading || list.data?.length !== 20}
          onPress={() => setOffset(offset + 20)}
        />
      </Card>
      {!writable ? (
        <Card>
          <Label>
            Salt okunur oturum. Profil yazmak için bilgisayarda açık
            profiles:write eşleştirme izni gerekir. Paper/scanner izni bu
            yetkiyi vermez.
          </Label>
        </Card>
      ) : (
        <Card>
          <Heading>
            {parent ? "Revizyon " + (parent.revision + 1) : "Yeni profil"}
          </Heading>
          {catalogue.error ? <Label>{catalogue.error}</Label> : null}
          {!locked ? (
            <>
              <Label>Stratejiler</Label>
              <Choices
                values={names("strategies", "strategy_id")}
                value={selection.strategy_ids || []}
                onChange={(v) => toggle("strategy_ids", v)}
              />
              <Label>Gerekli indikatörler · sabit dönemler</Label>
              <Choices
                values={names("methods", "method_id")}
                value={selection.required_methods || []}
                onChange={(v) => toggle("required_methods", v)}
              />
              <Label>Piyasa rejimleri</Label>
              <Choices
                values={["trend", "range", "breakout", "reversal"]}
                value={selection.allowed_regimes || []}
                onChange={(v) => toggle("allowed_regimes", v)}
              />
              {(
                [
                  "bias_timeframe",
                  "setup_timeframe",
                  "trigger_timeframe",
                ] as const
              ).map((k) => (
                <React.Fragment key={k}>
                  <Label>
                    {k === "bias_timeframe"
                      ? "Ana trend"
                      : k === "setup_timeframe"
                        ? "Kurulum"
                        : "Tetikleyici"}{" "}
                    zaman dilimi
                  </Label>
                  <Choices
                    values={timeframes}
                    value={selection[k] || "1H"}
                    onChange={(v) => setSelection({ ...selection, [k]: v })}
                  />
                </React.Fragment>
              ))}
              <Label>Bağımsız teyit sayısı</Label>
              <Choices
                values={["2", "3", "4", "5"]}
                value={String(selection.minimum_confirmations)}
                onChange={(v) =>
                  setSelection({
                    ...selection,
                    minimum_confirmations: Number(v),
                  })
                }
              />
              <Label>Araştırma sıklığı · kapalı mum sayısı</Label>
              <Choices
                values={["1", "5", "10", "30", "60"]}
                value={String(selection.analysis_every_bars)}
                onChange={(v) =>
                  setSelection({ ...selection, analysis_every_bars: Number(v) })
                }
              />
            </>
          ) : (
            <Label>
              İstek sonuçlanana kadar parametreler kilitli. Belirsiz yanıtta
              aynı komut yeniden gönderilir.
            </Label>
          )}
          <Label muted>
            Zaman dilimleri aynı olmalı veya ana trend &gt; kurulum &gt;
            tetikleyici sıralanmalı. Parametreler sunucuda doğrulanır. Sıklık
            seçimi kendiliğinden tarayıcı başlatmaz.
          </Label>
          {error ? <Label>{error}</Label> : null}
          <Button
            title={
              busy
                ? "Kaydediliyor…"
                : uncertain
                  ? "Aynı kaydı yeniden dene"
                  : "Profili kaydet"
            }
            disabled={
              busy || catalogue.loading || !!catalogue.error || !catalogue.data
            }
            onPress={save}
          />
          {parent && !locked ? (
            <Button
              title="Revizyonu bırak, yeni profil hazırla"
              onPress={() => {
                setParent(null);
                setSelection(initial);
              }}
            />
          ) : null}
        </Card>
      )}
    </>
  );
}
