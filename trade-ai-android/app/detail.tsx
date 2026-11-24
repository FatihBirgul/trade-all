import { ResearchDetails } from "../src/ResearchDetails";
import {
  hasMarketEvaluation,
  notEvaluated,
  regimeText,
  validityText,
} from "../src/domain/analysisPresentation";
import React, { useState } from "react";
import * as Crypto from "expo-crypto";
import { comparable } from "../src/domain/records";
import { useLocalSearchParams, router } from "expo-router";
import { useAnalysisRecord } from "../src/useAnalysisRecord";
import { useApp } from "../src/state";
import { useResource } from "../src/resource";
import { snapshotMatches } from "../src/domain/snapshot";
import { Metrics, SnapshotChart, field, object } from "../src/analysisView";
import { useAnalysisDecision } from "../src/useAnalysisDecision";
import {
  directionText,
  reasonText,
  technicalStatusText,
} from "../src/domain/presentation";
import {
  Button,
  Card,
  Empty,
  Failure,
  Heading,
  Label,
  Loading,
  Page,
  Row,
} from "../src/ui";
export default function Detail() {
  const { id, compare } = useLocalSearchParams<{
    id: string;
    compare?: string;
  }>();
  const app = useApp();
  const q = useAnalysisRecord(id);
  const comparison = useResource(async () => {
    if (!compare) return null;
    return app.mode === "demo"
      ? app.history.find(
          (row) => row.analysis_id === compare && row.data_mode === "fixture",
        )
      : app.api.detail(compare);
  }, [app.mode, app.connectionKey, app.config.session, compare].join("|"));
  const a = q.data;
  const decision = useAnalysisDecision(a);
  const evaluated = !!a && hasMarketEvaluation(a);
  const [loadCandles, setLoadCandles] = useState(false);
  const candles = useResource(async () => {
    if (!loadCandles || app.mode !== "live" || !a) return null;
    const c = await app.api.candles(a.analysis_id, a.timeframe);
    if (!snapshotMatches(a, c))
      throw new Error("Analiz mumlarının kaynağı doğrulanamadı.");
    return c;
  }, [app.mode, app.connectionKey, app.config.session, id, a?.analysis_id, loadCandles].join("|"));
  return (
    <Page mode={app.mode} connection={app} headerShown>
      {q.loading ? (
        <Loading />
      ) : q.error ? (
        <Failure message={q.error} retry={q.reload} />
      ) : !a ? (
        <Empty text="Analiz bulunamadı." />
      ) : (
        <>
          <Card>
            <Heading>
              {a.symbol} · {a.timeframe}
            </Heading>
            <Row name="Karar" value={directionText(decision)} />
            <Row name="Risk hesabı" value={a.risk_portfolio} />
            <Label muted>{validityText(a)}</Label>
            <Row
              name="Kayıtlı geçerlilik sonu"
              value={new Date(a.expires_at_ms).toLocaleString("tr-TR")}
            />
            {a.data_mode === "live" &&
            decision === "WAIT" &&
            a.direction !== "WAIT" ? (
              <Label muted>
                Analizin süresi veya güvenlik koşulları uygun değil. Yeni analiz
                alın; seviyeler kapatıldı.
              </Label>
            ) : null}
            <Row name="Karar gerekçesi" value={reasonText(a.reason)} />
            <Row
              name="Son kapalı mum"
              value={
                a.price_time_ms
                  ? new Date(a.price_time_ms).toLocaleString("tr-TR")
                  : "Yok · piyasa verisi alınmadı"
              }
            />
            <Row
              name="Analiz zamanı"
              value={new Date(a.created_at_ms).toLocaleString("tr-TR")}
            />
            <Row
              name="Veri kaynağı"
              value={
                a.provider === "fixture_spot" ? "Yerel DEMO örneği" : a.provider
              }
            />
            {a.warnings
              .filter((w) => w !== "Yerel DEMO örneği; piyasa verisi alınmadı.")
              .map((w, i) => (
                <Label key={i} muted>
                  {w}
                </Label>
              ))}
          </Card>
          <Button
            title="Yeni analiz al"
            secondary
            onPress={() => {
              app.setAccount(a.risk_portfolio);
              router.push({
                pathname: "/analysis",
                params: {
                  symbol: a.symbol,
                  timeframe: a.timeframe,
                  mtf: a.timeframes.filter((t) => t !== a.timeframe).join(","),
                  previous: a.analysis_id,
                  requestId: Crypto.randomUUID(),
                },
              });
            }}
          />
          <Button title="Kaydı yeniden yükle" secondary onPress={q.reload} />
          {compare ? (
            <Card>
              <Heading>Analiz karşılaştırması</Heading>
              {comparison.loading ? (
                <Loading />
              ) : comparison.error ? (
                <Failure message={comparison.error} retry={comparison.reload} />
              ) : comparison.data && comparable(a, comparison.data) ? (
                <>
                  <Row
                    name="Bu kayıt"
                    value={new Date(a.created_at_ms).toLocaleString("tr-TR")}
                  />
                  <Row
                    name="Diğer kayıt"
                    value={new Date(
                      comparison.data.created_at_ms,
                    ).toLocaleString("tr-TR")}
                  />
                  <Row
                    name="Kaydedilen karar · bu / diğer"
                    value={
                      directionText(a.direction) +
                      " / " +
                      directionText(comparison.data.direction)
                    }
                  />
                  <Row
                    name="Kaydedilen fiyat · bu / diğer"
                    value={
                      field(a.price) + " / " + field(comparison.data.price)
                    }
                  />
                  <Row
                    name="Piyasa rejimi · bu / diğer"
                    value={regimeText(a) + " / " + regimeText(comparison.data)}
                  />
                  <Row
                    name="Gerekçe · bu / diğer"
                    value={
                      reasonText(a.reason) +
                      " / " +
                      reasonText(comparison.data.reason)
                    }
                  />
                  <Row
                    name="Strateji · bu / diğer"
                    value={
                      field(a.router.strategy_id) +
                      " / " +
                      field(comparison.data.router.strategy_id)
                    }
                  />
                  {["rsi14", "macd", "ema20", "ema50"].map((key) => (
                    <Row
                      key={key}
                      name={key + " · bu / diğer"}
                      value={
                        field(a.indicators[key]) +
                        " / " +
                        field(comparison.data!.indicators[key])
                      }
                    />
                  ))}
                  <Label muted>
                    Tarihsel kayıt karşılaştırmasıdır. Süresi dolmuş kararlar
                    aktif fırsat değildir.
                  </Label>
                </>
              ) : (
                <Label>
                  Bu kayıtlar aynı piyasa, zaman dilimi, veri modu ve hesaba ait
                  değil.
                </Label>
              )}
            </Card>
          ) : null}
          {evaluated ? (
            <>
              <Card>
                <Heading>Teknik görünüm</Heading>
                {decision === "WAIT" ? (
                  <Label muted>
                    Bekle · {reasonText(a.reason)} Göstergeler varsa yalnız
                    bilgi amaçlıdır.
                  </Label>
                ) : null}
                <Metrics
                  items={Object.keys(a.indicators)
                    .filter(
                      (key) =>
                        a.indicators[key] === null ||
                        ["number", "string"].includes(typeof a.indicators[key]),
                    )
                    .map((k) => ({
                      name:
                        k === "rsi14"
                          ? "RSI 14 · mevcut gösterge"
                          : k === "macd_signal"
                            ? "MACD sinyali"
                            : k.toUpperCase(),
                      value: field(a.indicators[k]),
                    }))}
                />
                <Label muted>
                  Mevcut RSI14, stratejinin Wilder RSI14 hesabıyla aynı
                  değildir.
                </Label>
                <Metrics
                  items={["fvg", "structure", "liquidity_sweep", "vwap"].map(
                    (k) => {
                      const method = object(a.technical_methods?.[k]);
                      const extra =
                        k === "vwap"
                          ? field(method.value)
                          : k === "fvg" && Array.isArray(method.active_gaps)
                            ? method.active_gaps.length + " aktif boşluk"
                            : k === "structure"
                              ? field(method.bias)
                              : k === "liquidity_sweep" &&
                                  typeof method.direction === "string"
                                ? directionText(method.direction)
                                : "";
                      return {
                        name:
                          k === "structure"
                            ? "BOS / CHoCH"
                            : k === "liquidity_sweep"
                              ? "Likidite süpürmesi"
                              : k.toUpperCase(),
                        value:
                          technicalStatusText(method.status) +
                          (extra ? " · " + extra : ""),
                      };
                    },
                  )}
                />
              </Card>
              <Card>
                <Heading>Rejim ve Strategy Router</Heading>
                <Row name="Rejim" value={regimeText(a)} />
                <Row
                  name="Router durumu"
                  value={technicalStatusText(a.router.status)}
                />
                <Row
                  name="Seçilen strateji"
                  value={field(a.router.strategy_id)}
                />
                <Row
                  name="MTF yönü"
                  value={
                    object(a.mtf.current).available === true
                      ? directionText(field(a.mtf.direction))
                      : notEvaluated
                  }
                />
                {[
                  "higher_timeframe_alignment",
                  "lower_timeframe_confirmation",
                ].map((key) => {
                  const confirmation = object(a.mtf[key]);
                  return (
                    <Row
                      key={key}
                      name={
                        key === "higher_timeframe_alignment"
                          ? "Üst zaman dilimi teyidi"
                          : "Alt zaman dilimi teyidi"
                      }
                      value={
                        (Number(confirmation.available_count) > 0
                          ? directionText(field(confirmation.direction))
                          : "Değerlendirilemedi") +
                        " · " +
                        field(confirmation.supporting_count) +
                        " destek / " +
                        field(confirmation.opposing_count) +
                        " karşıt"
                      }
                    />
                  );
                })}
                <Row
                  name="Router gerekçesi"
                  value={reasonText(field(a.router.reason))}
                />
                <Row name="Zaman dilimleri" value={a.timeframes.join(" · ")} />
                {Object.entries(a.strategy_setups ?? {}).map(([key, value]) => (
                  <Row
                    key={key}
                    name={key}
                    value={
                      technicalStatusText(object(value).status) +
                      " · " +
                      directionText(field(object(value).direction)) +
                      " · " +
                      reasonText(field(object(value).reason)) +
                      " · Wilder RSI14: " +
                      field(object(object(value).momentum).rsi14_wilder)
                    }
                  />
                ))}
              </Card>
            </>
          ) : (
            <Card>
              <Heading>Teknik değerlendirme</Heading>
              <Label muted>{notEvaluated}</Label>
            </Card>
          )}
          {app.mode === "live" ? (
            <Card>
              <Heading>Analizin mum kaydı</Heading>
              {!loadCandles ? (
                <Button
                  title="Analiz mumlarını yükle"
                  secondary
                  onPress={() => setLoadCandles(true)}
                />
              ) : candles.loading ? (
                <Loading />
              ) : candles.error ? (
                <Failure message={candles.error} retry={candles.reload} />
              ) : candles.data ? (
                <SnapshotChart
                  key={candles.data.analysis_id + "|" + app.uiMode}
                  snapshot={candles.data}
                  pro={app.uiMode === "pro"}
                  levels={decision !== "WAIT" ? a.levels : null}
                />
              ) : null}
            </Card>
          ) : null}
          <ResearchDetails methods={a.technical_methods} />
          {decision !== "WAIT" && a.levels ? (
            <Card>
              <Heading>Koşullu seviyeler</Heading>
              <Row
                name="Giriş"
                value={a.levels.entry_low + " – " + a.levels.entry_high}
              />
              <Row name="Geçersizlik seviyesi" value={a.levels.invalidation} />
              <Row name="TP1" value={a.levels.target_1} />
              <Row name="TP2" value={a.levels.target_2} />
            </Card>
          ) : (
            <Card>
              <Label>Bekle · İşlem seviyeleri ve emir oluşturma kapalı.</Label>
            </Card>
          )}
        </>
      )}
    </Page>
  );
}
