import { SnapshotResearchControls } from "../src/SnapshotResearchControls";
import { FollowPolicyControls } from "../src/FollowPolicyControls";
import { ResearchDetails } from "../src/ResearchDetails";
import {
  hasMarketEvaluation,
  validityText,
} from "../src/domain/analysisPresentation";
import React, { useRef, useState, useEffect } from "react";
import { useResource } from "../src/resource";
import { router, useLocalSearchParams } from "expo-router";
import { useApp } from "../src/state";
import { useAnalysisRecord } from "../src/useAnalysisRecord";
import { useAnalysisDecision } from "../src/useAnalysisDecision";
import { userErrorText, reasonText } from "../src/domain/presentation";
import { SnapshotPanel } from "../src/SnapshotPanel";
import { object } from "../src/analysisView";
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
  Disclosure,
} from "../src/ui";
export default function Result() {
  const { id, compare } = useLocalSearchParams<{
    id: string;
    compare?: string;
  }>();
  const app = useApp(),
    query = useAnalysisRecord(id),
    a = query.data;
  const decision = useAnalysisDecision(a);
  const [following, setFollowing] = useState(false),
    [followMessage, setFollowMessage] = useState({ scope: "", text: "" });
  const scope = [app.mode, app.connectionKey, app.config.session, id].join("|");
  const currentScope = useRef(scope);
  useEffect(() => {
    currentScope.current = scope;
  }, [scope]);
  const follows = useResource(
    async () =>
      app.mode === "live" &&
      app.gatewayVerified &&
      app.sessionInfo?.capabilities?.includes("analysis-follow-v1")
        ? app.api.follows()
        : [],
    scope +
      "|" +
      app.gatewayVerified +
      "|" +
      app.sessionInfo?.capabilities?.join(","),
  );
  const track =
    follows.data?.find(
      (row) =>
        row.enabled &&
        !!a &&
        row.symbol === a.symbol &&
        row.timeframe === a.timeframe &&
        row.portfolio_id === a.risk_portfolio,
    ) ??
    follows.data?.find(
      (row) => row.origin_analysis_id === id || row.last_analysis_id === id,
    );
  const canFollow =
    app.mode === "live" &&
    app.sessionInfo?.capabilities?.includes("analysis-follow-v1") &&
    app.gatewayVerified &&
    app.sessionInfo?.scopes.includes("scanner:write") &&
    !!a &&
    app.sessionInfo.accounts.includes(a.risk_portfolio);
  async function followAction() {
    if (!canFollow || following || !a) return;
    const attempted = scope;
    setFollowing(true);
    setFollowMessage({ scope: attempted, text: "" });
    try {
      if (track) await app.api.changeFollow(track.tracking_id, !track.enabled);
      else await app.api.follow(a.analysis_id);
      if (currentScope.current === attempted) follows.reload();
    } catch (error) {
      if (currentScope.current === attempted) {
        setFollowMessage({ scope: attempted, text: userErrorText(error) });
        follows.reload();
      }
    } finally {
      setFollowing(false);
    }
  }

  const selectedStrategy =
    a && typeof a.router.strategy_id === "string"
      ? object(a.strategy_setups?.[a.router.strategy_id])
      : {};
  const reasons = a
    ? hasMarketEvaluation(a)
      ? [
          ...new Set([
            a.quality.ok === true
              ? "Veri kalitesi kontrolü geçti."
              : "Veri kalitesi veya teyitler eksik.",
            ...[a.router.reason, selectedStrategy.reason]
              .filter(
                (value): value is string =>
                  typeof value === "string" && value !== a.reason,
              )
              .map(summaryReason),
          ]),
        ].slice(0, 3)
      : ["Piyasa değerlendirmesi yapılmadı; bu kayıt işlem senaryosu değildir."]
    : [];

  return (
    <Page mode={app.mode} connection={app} headerShown>
      {query.loading ? (
        <Loading />
      ) : query.error ? (
        <Failure message={query.error} retry={query.reload} />
      ) : !a ? (
        <Empty text="Analiz bulunamadı." />
      ) : (
        <>
          <Heading>
            {a.symbol} · {a.timeframe}
          </Heading>
          <Card elevated>
            <Heading>
              {decision === "WAIT"
                ? "BEKLE"
                : decision === "bullish"
                  ? "Koşullu yükseliş"
                  : "Koşullu düşüş"}
            </Heading>
            <Label>
              {decision === "WAIT" && a.direction !== "WAIT"
                ? "Bu kaydın güncellik veya güvenlik koşulları artık uygun değil. Yeni analiz alın."
                : summaryReason(a.reason)}
            </Label>
            {reasons.map((text) => (
              <Label key={text} muted>
                • {text}
              </Label>
            ))}
            <Label muted>
              {a.data_mode === "fixture"
                ? "DEMO · örnek veri"
                : "Kayıtlı piyasa verisi"}{" "}
              ·{" "}
              {a.price_time_ms
                ? new Date(a.price_time_ms).toLocaleString("tr-TR")
                : "Veri alınamadı"}
            </Label>
          </Card>
          {app.uiMode !== "basic" ? (
            <SnapshotPanel
              key={scope}
              analysis={a}
              levelsAllowed={decision !== "WAIT"}
            />
          ) : null}
          {app.mode === "live" ? (
            app.uiMode === "basic" ? (
              <Card>
                <Row
                  name="Takip"
                  value={
                    follows.loading
                      ? "Kontrol ediliyor…"
                      : follows.error
                        ? "Doğrulanamadı · bağlantı yok"
                        : track
                          ? track.enabled
                            ? "Açık"
                            : "Duraklatıldı"
                          : "Kayıt yok"
                  }
                />
                {track && !follows.error ? (
                  <Label muted>
                    {track.worker_running
                      ? "PC işçisi son sorguda çalışıyordu."
                      : "PC işçisi kapalı; otomatik takip başlamadı."}
                  </Label>
                ) : null}
                <Button
                  title="Takipleri yönet"
                  variant="ghost"
                  onPress={() =>
                    router.push({
                      pathname: "/follows",
                      params: { analysis: a.analysis_id },
                    })
                  }
                />
              </Card>
            ) : (
              <Card>
                <Heading>Analiz takip asistanı</Heading>
                {follows.loading ? (
                  <Label muted>Takip durumu kontrol ediliyor…</Label>
                ) : follows.error ? (
                  <Label>
                    Bağlantı yok · takip durumu doğrulanamadı. {follows.error}
                  </Label>
                ) : track ? (
                  <>
                    <Row
                      name="Takip"
                      value={track.enabled ? "Açık" : "Duraklatıldı"}
                    />
                    <Row
                      name="PC işçisi"
                      value={
                        track.worker_running
                          ? "Son sorguda çalışıyordu"
                          : "Kapalı · otomatik takip başlamadı"
                      }
                    />
                    <Label muted>
                      {track.last_checked_ms
                        ? "Son kontrol: " +
                          new Date(track.last_checked_ms).toLocaleString(
                            "tr-TR",
                          )
                        : "Henüz yeniden değerlendirilmedi."}
                    </Label>
                    <Label muted>{reasonText(track.last_reason)}</Label>
                    {track.last_analysis_id !== a.analysis_id ? (
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
                    ) : null}
                  </>
                ) : (
                  <Label muted>Bu piyasa için takip kaydı yok.</Label>
                )}
                {track && !follows.error ? (
                  <FollowPolicyControls
                    key={scope + "|" + track.tracking_id}
                    id={track.tracking_id}
                    account={track.portfolio_id}
                  />
                ) : null}
                {canFollow ? (
                  <Button
                    title={
                      following
                        ? "Takip kaydı işleniyor…"
                        : track?.enabled
                          ? "Takibi durdur"
                          : track
                            ? "Takibe devam et"
                            : "Bu analizi takip et"
                    }
                    secondary
                    disabled={following || follows.loading || !!follows.error}
                    onPress={followAction}
                  />
                ) : (
                  <Label muted>
                    Takip için CANLI bağlantı ve hesabın scanner yetkisi
                    gerekir.
                  </Label>
                )}
                <Button
                  title="Takip durumunu yenile"
                  variant="ghost"
                  disabled={follows.loading}
                  onPress={follows.reload}
                />
                <Button
                  title="Takipleri yönet"
                  variant="ghost"
                  onPress={() =>
                    router.push({
                      pathname: "/follows",
                      params: { analysis: a.analysis_id },
                    })
                  }
                />
                {followMessage.scope === scope && followMessage.text ? (
                  <Label>{followMessage.text}</Label>
                ) : null}
              </Card>
            )
          ) : (
            <Label muted>Takip asistanı CANLI bağlantıda kullanılabilir.</Label>
          )}
          <Button
            title="Detaylı analizi aç"
            onPress={() =>
              router.push({
                pathname: "/detail",
                params: { id: a.analysis_id, ...(compare ? { compare } : {}) },
              })
            }
          />
          <Disclosure title="Gelişmiş araştırma ve parametreler">
            <ResearchDetails methods={a.technical_methods} />
            <SnapshotResearchControls analysis={a} />
          </Disclosure>
          <Disclosure title="Kaynak, risk ve teknik notlar">
            <Card>
              <Row
                name="Kaynak"
                value={
                  a.data_mode === "fixture" ? "DEMO · örnek veri" : a.provider
                }
              />
              <Row
                name="Analiz zamanı"
                value={new Date(a.created_at_ms).toLocaleString("tr-TR")}
              />
              <Label muted>{validityText(a)}</Label>
              <Row
                name="Kayıtlı geçerlilik sonu"
                value={new Date(a.expires_at_ms).toLocaleString("tr-TR")}
              />
              <Row name="Hesap" value={a.risk_portfolio + " · sanal"} />
              <Label muted>
                {decision === "WAIT"
                  ? "Bekleme kararı alım/satım fırsatı değildir. Aktif işlem seviyeleri gösterilmez."
                  : "Yön koşulludur; başarı veya kârlılık garantisi değildir."}
              </Label>
              <Label muted>
                Haber/takvim, emir defteri, fonlama ve likidasyon akışları
                doğrulanmış teyit olarak kullanılmaz.
              </Label>
              {(hasMarketEvaluation(a)
                ? Object.entries(a.strategy_setups ?? {})
                : []
              ).map(([key, value]) => (
                <Label key={key}>
                  {strategyName(key)}:{" "}
                  {typeof object(value).reason === "string"
                    ? summaryReason(String(object(value).reason))
                    : "Değerlendirme alınamadı."}
                </Label>
              ))}
              <Label muted>
                Bildirimler pending outbox kaydıdır; Android push teslimi
                yoktur.
              </Label>
            </Card>
          </Disclosure>
        </>
      )}
    </Page>
  );
}

export function strategyName(key: string) {
  return (
    (
      {
        trend_momentum_v2: "Trend ve momentum",
        confirmed_breakout_v2: "Teyitli kırılım",
        failed_breakout_v2: "Başarısız kırılım",
        range_mean_reversion_v2: "Yatay aralık dönüşü",
      } as Record<string, string>
    )[key] ?? "Strateji değerlendirmesi"
  );
}

function summaryReason(code: string) {
  const result = reasonText(code);
  return result.startsWith("Neden kodu:")
    ? "Sunucu bu koşul için ayrıntılı bir açıklama sağlamadı. Teknik ayrıntılardan kontrol edin."
    : result;
}
