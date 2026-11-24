/** Pure research on actual immutable source candles; never live strategy settings. */
import React, { useRef, useState, useEffect } from "react";
import { TextInput } from "react-native";
import { useApp } from "./state";
import { useTheme } from "./theme";
import { useResource } from "./resource";
import { ApiError } from "./api/client";
import type { components } from "./api/schema";
import { Button, Card, Heading, Label, Row, Disclosure } from "./ui";
import { object } from "./analysisView";
import { userErrorText } from "./domain/presentation";
type Models = components["schemas"];
const periods = [
  ["ema_period", "EMA"],
  ["sma_period", "SMA"],
  ["rsi_period", "RSI"],
  ["macd_fast", "MACD hızlı"],
  ["macd_slow", "MACD yavaş"],
  ["macd_signal", "MACD sinyal"],
  ["atr_period", "ATR"],
  ["adx_period", "ADX"],
  ["supertrend_period", "Supertrend"],
  ["donchian_period", "Donchian"],
  ["stochastic_period", "Stochastic"],
  ["stochastic_smooth", "Stochastic düzeltme"],
  ["bollinger_period", "Bollinger"],
] as const;
export function SnapshotResearchControls({
  analysis,
}: {
  analysis: Models["AnalysisResponse"];
}) {
  const app = useApp();
  const key = [
    app.mode,
    app.connectionKey,
    app.config.session,
    analysis.analysis_id,
    analysis.risk_portfolio,
  ].join("|");
  const supported =
    app.mode === "live" &&
    app.gatewayVerified &&
    !!app.sessionInfo?.capabilities?.includes("snapshot-research-v1") &&
    !!app.sessionInfo.accounts.includes(analysis.risk_portfolio);
  return <Controls key={key} analysis={analysis} supported={supported} />;
}
function Controls({
  analysis,
  supported,
}: {
  analysis: Models["AnalysisResponse"];
  supported: boolean;
}) {
  const app = useApp();
  const { colors } = useTheme();
  const alive = useRef(true);
  useEffect(
    () => () => {
      alive.current = false;
    },
    [],
  );
  const q = useResource(
    async () =>
      supported
        ? app.api.researchCatalogue(
            analysis.analysis_id,
            analysis.risk_portfolio,
          )
        : null,
    analysis.analysis_id + "|" + supported,
  );
  const [index, setIndex] = useState<number | null>(null),
    [values, setValues] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<Models["SnapshotResearchResponse"] | null>(
      null,
    );
  const lock = useRef(false);
  const cat = q.data;
  const anchors = cat?.anchors ?? [];
  const selected = Math.min(
    index ?? Math.max(0, anchors.length - 2),
    Math.max(0, anchors.length - 1),
  );
  const anchor = anchors[selected];
  const clear = () => {
    setResult(null);
    setError("");
  };
  async function calculate() {
    if (!cat || !anchor || busy || lock.current || !supported || q.stale)
      return;
    lock.current = true;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const parameters: Record<string, number | string> = {};
      for (const [key, value] of Object.entries(values)) {
        if (!value.trim()) continue;
        if (
          !/^\d{1,3}$/.test(value) ||
          Number(value) < 1 ||
          Number(value) > 200
        )
          throw new ApiError("INVALID_RESEARCH_PARAMETERS");
        parameters[key] = Number(value);
      }
      const r = await app.api.computeResearch(
        analysis.analysis_id,
        analysis.risk_portfolio,
        {
          source_record_id: cat.source_record_id,
          symbol: cat.symbol as Models["SnapshotResearchRequest"]["symbol"],
          timeframe:
            cat.timeframe as Models["SnapshotResearchRequest"]["timeframe"],
          anchor_ms: anchor.open_time_ms,
          parameters,
        },
      );
      if (alive.current) setResult(r);
    } catch (e) {
      if (alive.current) setError(userErrorText(e));
    } finally {
      lock.current = false;
      if (alive.current) setBusy(false);
    }
  }
  const anchored = object(result?.anchored_vwap),
    indicators = object(result?.indicator_research),
    methods = object(indicators.methods);
  return (
    <Card>
      <Heading>Kaynak mumundan araştırma</Heading>
      <Label muted>
        Yalnız tarihsel analiz kaydı. Anchor ve parametre seçimi canlı
        stratejiyi, BEKLE kararını veya işlem iznini değiştirmez.
      </Label>
      {!supported ? (
        <Label>
          Bu araştırma için güncel Gateway ve hesabın okuma yetkisi gerekli.
          Demo sonuç üretilmedi.
        </Label>
      ) : (
        <>
          {q.loading ? <Label>Kaynak mumları yükleniyor…</Label> : null}
          {q.error ? (
            <>
              <Label>{q.error}</Label>
              <Button title="Kaynağı yeniden oku" onPress={q.reload} />
            </>
          ) : null}
          {cat?.status === "unavailable" ? (
            <Label>Kaynak araştırmaya uygun değil: {cat.reason}</Label>
          ) : null}
          {cat?.status === "available" ? (
            <>
              <Row name="Kayıt" value={cat.timeframe + " · " + cat.source} />
              <Label muted>
                Analiz zamanı: {new Date(cat.as_of_ms).toISOString()} ·{" "}
                {cat.data_mode === "fixture"
                  ? "Fixture / test kaydı"
                  : "Kaydedilmiş piyasa kaynağı"}
              </Label>
              {!anchor ? (
                <Label>Gerçek hacimli uygun anchor mumu yok.</Label>
              ) : (
                <>
                  <Label>
                    Anchor: {new Date(anchor.open_time_ms).toISOString()}
                  </Label>
                  <Label muted>
                    En son {anchors.length} uygun kapalı mum arasından seçim. En
                    az iki kapalı kaynak mumu gerekir.
                  </Label>
                  <Button
                    title="Önceki anchor mumu"
                    disabled={busy || selected === 0}
                    onPress={() => {
                      setIndex(selected - 1);
                      clear();
                    }}
                  />
                  <Button
                    title="Sonraki anchor mumu"
                    disabled={busy || selected === anchors.length - 1}
                    onPress={() => {
                      setIndex(selected + 1);
                      clear();
                    }}
                  />
                  <Disclosure title="Bağımsız indikatör araştırma parametreleri">
                    <Label muted>
                      Boş alan kayıtlı varsayılanı kullanır. Backend
                      whitelist/sınır ve MACD sırası doğrulamasını uygular.
                      Profil veya canlı strateji ayarı değildir.
                    </Label>
                    {periods.map(([key, label]) => (
                      <React.Fragment key={key}>
                        <Label>
                          {label} periyodu · varsayılan{" "}
                          {String(cat.parameters[key])}
                        </Label>
                        <TextInput
                          accessibilityLabel={label + " araştırma periyodu"}
                          keyboardType="number-pad"
                          maxLength={3}
                          editable={!busy}
                          value={values[key] ?? ""}
                          onChangeText={(v) => {
                            setValues((old) => ({ ...old, [key]: v }));
                            clear();
                          }}
                          style={{
                            backgroundColor: colors.card,
                            color: colors.text,
                            padding: 10,
                            borderRadius: 8,
                          }}
                        />
                      </React.Fragment>
                    ))}
                  </Disclosure>
                  <Button
                    title={
                      busy
                        ? "Araştırma hesaplanıyor…"
                        : "Seçili kaynakla araştırmayı hesapla"
                    }
                    disabled={busy || q.stale}
                    onPress={calculate}
                  />
                </>
              )}
            </>
          ) : null}
          {error ? <Label>{error}</Label> : null}
          {result ? (
            <>
              <Row
                name="Anchored VWAP"
                value={
                  anchored.status === "available"
                    ? String(anchored.value)
                    : "Kullanılamıyor"
                }
              />
              <Label muted>
                Gerçek hacim ile mum tipik fiyatının ağırlıklı ortalaması;
                tick/trade VWAP veya işlem teyidi değildir.
              </Label>
              {anchored.reason ? (
                <Label>{String(anchored.reason)}</Label>
              ) : null}
              <Label>
                İndikatör durumu:{" "}
                {indicators.status === "available"
                  ? "Hesaplandı"
                  : "Yetersiz / uygun olmayan veri"}
              </Label>
              {indicators.reason ? (
                <Label>{String(indicators.reason)}</Label>
              ) : null}
              {Object.entries(methods).map(([k, v]) => (
                <Row
                  key={k}
                  name={k}
                  value={v === null ? "Tanımsız" : String(v)}
                />
              ))}
              <Label muted>
                Konfigürasyon: {result.configuration_id} · Isınma:{" "}
                {result.warmup_bars} mum. Kanıt: INSUFFICIENT_EVIDENCE.
              </Label>
            </>
          ) : null}
        </>
      )}
    </Card>
  );
}
