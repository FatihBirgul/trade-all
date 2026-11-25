import { BrandMark } from "../../src/BrandMark";
import React, { useState } from "react";
import { View } from "react-native";
import { router } from "expo-router";
import * as Crypto from "expo-crypto";
import { useMarketQuotes } from "../../src/useMarketQuotes";
import { validatePortfolio } from "../../src/domain/portfolio";
import { MarketRow } from "../../src/MarketRow";
import { directionText } from "../../src/domain/presentation";
import { useResource } from "../../src/resource";
import { useApp } from "../../src/state";
import { useTheme } from "../../src/theme";
import {
  Button,
  Card,
  Heading,
  Label,
  Page,
  Row,
  Choices,
  Failure,
  Loading,
  ScreenHeader,
  SectionHeader,
} from "../../src/ui";
import {
  symbols,
  money,
  emptyPortfolio,
  safeDecision,
} from "../../src/domain/safety";
export default function Home() {
  const app = useApp();
  const { colors } = useTheme();
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const scope = [app.mode, app.connectionKey, app.config.session].join("|");
  const recent = useResource(
    async () =>
      app.mode === "demo"
        ? app.history.filter((a) => a.data_mode === "fixture").slice(0, 3)
        : app.api.analyses(),
    scope + "|" + app.history.length,
  );
  const prices = useMarketQuotes();
  const portfolios = useResource(
    async () =>
      app.mode === "demo"
        ? (["AUTO", "MANUAL"] as const).map(emptyPortfolio)
        : app.api.portfolios().then((rows) => {
            rows.forEach((p) => {
              if (!app.sessionInfo?.accounts.includes(p.portfolio_id))
                throw new Error("Hesap yetkisi doğrulanamadı.");
              validatePortfolio(p, p.portfolio_id);
            });
            return rows;
          }),
    scope,
  );
  const supported = app.sessionInfo?.capabilities?.includes("market-quotes-v1");
  function analyze(market: string) {
    router.push({
      pathname: "/analysis",
      params: { symbol: market, requestId: Crypto.randomUUID() },
    });
  }
  return (
    <Page mode={app.mode} connection={app}>
      <BrandMark compact />
      <ScreenHeader
        title="Piyasaya bakış"
        badge={app.uiMode === "pro" ? "PRO" : "BASİT"}
      />
      <Button
        title="Tarayıcı ve fırsatlar"
        secondary
        onPress={() => router.push("/market-discovery")}
      />
      <SectionHeader
        title="Piyasalar"
        action={
          app.mode === "live"
            ? prices.loading
              ? "Yenileniyor…"
              : "Piyasayı yenile"
            : undefined
        }
        onPress={prices.loading || !supported ? undefined : prices.reload}
      />
      {app.mode === "demo" ? (
        <Label muted>
          Bu modda canlı fiyat alınmaz. Yerel örnekler gösterilir.
        </Label>
      ) : (
        <>
          {prices.stale ? (
            <Label style={{ color: colors.gold }}>
              Güncel değil · Son başarılı fiyatlar gösteriliyor.
            </Label>
          ) : null}
          {!supported ? (
            <Label muted>
              Piyasa verileri için güncel Gateway ve Backend gerekir.
            </Label>
          ) : null}
          {prices.error ? (
            <Label style={{ color: colors.red }}>{prices.error}</Label>
          ) : null}
          {prices.data ? (
            <Card elevated>
              {prices.data.items.map((quote) => (
                <MarketRow
                  key={quote.symbol}
                  quote={quote}
                  stale={prices.stale}
                  onPress={() => analyze(quote.symbol)}
                />
              ))}
              <Label muted>
                Binance Spot · Satıra dokunarak analiz açın. Grafik: son kapalı
                1 saatlik mumlar. Canlı mum grafiği değildir; analiz kaydından
                ayrıdır.
              </Label>
            </Card>
          ) : prices.loading ? (
            <Loading />
          ) : (
            <Card>
              <Label>
                Piyasa fiyatı yüklenemedi; örnek fiyat gösterilmedi.
              </Label>
            </Card>
          )}
        </>
      )}
      <Card elevated>
        <Heading>Hızlı analiz</Heading>
        <Label muted>
          {app.account} · yalnız analiz; otomatik emir oluşturmaz.
        </Label>
        <Choices values={symbols} value={symbol} onChange={setSymbol} />
        <Button title="Analiz Et" onPress={() => analyze(symbol)} />
      </Card>
      <SectionHeader
        title="Son analizler"
        action="Yenile"
        onPress={recent.loading ? undefined : recent.reload}
      />
      {recent.loading ? (
        <Loading />
      ) : recent.error ? (
        <Failure message={recent.error} retry={recent.reload} />
      ) : recent.data?.length ? (
        <Card>
          {recent.data.slice(0, app.uiMode === "pro" ? 3 : 1).map((a) => (
            <View key={a.analysis_id} style={{ gap: 6 }}>
              <Row
                name={a.symbol + " · " + a.timeframe}
                value={directionText(safeDecision(a))}
              />
              <Label muted>
                {new Date(a.created_at_ms).toLocaleString("tr-TR")}
              </Label>
              <Button
                title="Son analizi aç"
                variant="ghost"
                onPress={() =>
                  router.push({
                    pathname: "/result",
                    params: { id: a.analysis_id },
                  })
                }
              />
            </View>
          ))}
        </Card>
      ) : (
        <Label muted>Henüz analiz yüklenmedi.</Label>
      )}
      {app.uiMode === "pro" ? (
        <Button
          title="Analiz geçmişini aç"
          variant="ghost"
          onPress={() => router.push("/history")}
        />
      ) : null}
      <SectionHeader
        title={app.mode === "demo" ? "Örnek sanal portföy" : "Sanal portföy"}
        action="Portföyleri aç"
        onPress={() => router.push("/portfolios")}
      />
      {portfolios.loading ? (
        <Loading />
      ) : portfolios.error ? (
        <Failure message={portfolios.error} retry={portfolios.reload} />
      ) : portfolios.data?.length ? (
        <Card>
          {portfolios.data.map((p) => (
            <View key={p.portfolio_id} style={{ gap: 4 }}>
              <Row
                name={
                  p.portfolio_id +
                  (app.mode === "demo" ? " · DEMO hesabı" : " · Sanal hesap")
                }
                value={money(p.equity_quote) + " USDT"}
              />
              <Label muted>
                {p.open_positions} açık pozisyon · {p.pending_orders} bekleyen
                emir
              </Label>
            </View>
          ))}
          <Label muted>
            {app.mode === "demo"
              ? "Yerel örnek bakiyeler · backend sorgulanmadı."
              : "Backend’den alınan ayrı sanal hesaplar · gerçek para kullanılmaz."}
          </Label>
        </Card>
      ) : (
        <Label muted>Portföy verisi alınamadı.</Label>
      )}
      {app.uiMode === "pro" ? (
        <>
          <Button
            title="Tarayıcıyı aç"
            secondary
            onPress={() => router.push("/scanner")}
          />
          <Button
            title="Performans"
            variant="ghost"
            onPress={() => router.push("/performance")}
          />
        </>
      ) : null}
      {app.mode === "live" ? (
        <Button
          title="Analiz takipleri"
          variant="ghost"
          onPress={() => router.push("/follows")}
        />
      ) : null}
      <Button
        title="Bildirimler"
        variant="ghost"
        onPress={() => router.push("/notifications")}
      />
    </Page>
  );
}
