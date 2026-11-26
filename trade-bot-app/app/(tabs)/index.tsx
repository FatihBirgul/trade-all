import React, { useCallback, useRef, useState } from "react";
import { Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "expo-router";
import { setStatusBarStyle } from "expo-status-bar";
import { currentPeriodPnl } from "../../src/bot/periods";
import { REAL_ACTION_NOTE, agoText, amountText, botStateText, pnlText, vetoText } from "../../src/bot/presentation";
import { useBot } from "../../src/bot/state";
import { useConfirm } from "../../src/ui/confirm";
import { DataGate } from "../../src/ui/DataGate";
import { Button, Card, IconBubble, Notice, Pill, Row, Screen, T } from "../../src/ui/kit";
import { useResource } from "../../src/ui/useResource";
import { c, soft, tone } from "../../src/ui/theme";

const REFRESH_MS = 60_000;

export default function Panel() {
  const bot = useBot();
  const confirm = useConfirm();
  const ready = bot.phase === "ready";
  const week = useResource(ready ? () => bot.api.reports("week") : null, "week:" + bot.config?.origin, REFRESH_MS);
  const month = useResource(ready ? () => bot.api.reports("month") : null, "month:" + bot.config?.origin, REFRESH_MS);
  const summary = useResource(ready ? () => bot.api.summary() : null, "summary:" + bot.config?.origin, REFRESH_MS);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  const running = useRef(false); // çift dokunuş aynı isteği iki kez göndermesin
  // Panel'in üstü koyu renklidir: bu sekme görünürken durum çubuğu simgeleri açık olur.
  useFocusEffect(
    useCallback(() => {
      setStatusBarStyle("light");
      return () => setStatusBarStyle("dark");
    }, []),
  );
  const status = bot.status;
  const currency = status?.currency;

  async function run(action: () => Promise<unknown>, done: string) {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice({ text: done, bad: false });
    } catch (reason) {
      setNotice({ text: reason instanceof Error ? reason.message : "İşlem tamamlanamadı.", bad: true });
    } finally {
      running.current = false;
      setBusy(false);
      void bot.refresh();
    }
  }
  async function stop() {
    if (await confirm({ title: "Bot durdurulsun mu?", message: "Yeni işlem açılmaz. Açık işlemler zarar durdurmalarıyla birlikte yönetilmeye devam eder.", confirm: "Durdur", danger: true }))
      await run(() => bot.api.stop(), "Bot durduruldu.");
  }
  async function resume() {
    if (!status?.halted) {
      if (await confirm({ title: "Bot devam etsin mi?", message: "Bot yeniden işlem açabilir.", confirm: "Devam et" }))
        await run(() => bot.api.resume(false), "Bot devam ediyor.");
      return;
    }
    // Bot kendini kayıp sınırı yüzünden durdurdu: iki ayrı onay istenir.
    const first = await confirm({ title: "Bot kayıp sınırı nedeniyle durdu", message: "Neden: " + (status.halt_reason || "toplam kayıp sınırı") + ".\n\nDevam ederseniz kayıp ölçümü şimdiki bakiyeden yeniden başlar ve bot yeni işlem açabilir.", confirm: "Devam etmek istiyorum", danger: true });
    if (first && (await confirm({ title: "Emin misiniz?", message: "Kayıp sınırı koruması sıfırlanacak.", confirm: "Evet, devam et", danger: true })))
      await run(() => bot.api.resume(true), "Bot devam ediyor.");
  }
  async function closeAll() {
    const count = (status?.open_bot ?? 0) + (status?.open_manual ?? 0);
    const message = (count > 0 ? "Bot ve elle açılmış " + count + " pozisyonun tamamı piyasa fiyatından kapatılır ve bot durdurulur." : "Açık pozisyon görünmüyor; yine de varsa hepsi kapatılır ve bot durdurulur.") + " Bu işlem geri alınamaz." + (status?.dry_run ? "\n\n" + REAL_ACTION_NOTE : "");
    if (!(await confirm({ title: "Tüm pozisyonlar kapatılsın mı?", message, confirm: "Hepsini kapat", danger: true }))) return;
    await run(async () => {
      const result = await bot.api.closeAll();
      if (result.skipped?.length) throw new Error(result.requested + " pozisyon için kapama istendi; " + result.skipped.length + " pozisyonda zaten bekleyen bir kapama var. Pozisyonlar sekmesinden kontrol edin.");
    }, "Kapama istekleri gönderildi. Pozisyonlar sekmesinden izleyin.");
  }
  async function goLive() {
    // Canlı mod gerçek para ile emir gönderir: iki ayrı onay.
    const first = await confirm({ title: "Canlı moda geçilsin mi?", message: "Bot GERÇEK PARA ile emir göndermeye başlar ve kendi kararıyla işlem açar.\n\nKayıp sınırları şu anki varlık (" + amountText(status?.equity, currency) + ") üzerinden ölçülmeye başlar.", confirm: "Canlıya geçmek istiyorum", danger: true });
    if (first && (await confirm({ title: "Emin misiniz?", message: "Bu andan itibaren bot gerçek hesapta işlem açabilir.", confirm: "Evet, canlıya geç", danger: true })))
      await run(() => bot.api.setDryRun(false), "Canlı moda geçildi.");
  }
  async function goDry() {
    if (await confirm({ title: "Deneme moduna dönülsün mü?", message: "Bot yeni işlem açmaz ve açık işlemlerde kademeli stop yapmaz. Mevcut stop ve hedef emirleri Exness’te kalır.", confirm: "Deneme moduna dön" }))
      await run(() => bot.api.setDryRun(true), "Deneme moduna geçildi.");
  }

  const state = status ? botStateText(status) : null;
  const stateColor = state ? { ok: c.up, warn: c.sun, bad: c.down }[state.tone] : c.muted;
  const stateSoft = state ? { ok: c.upSoft, warn: c.sunSoft, bad: c.downSoft }[state.tone] : c.line;
  const nowSeconds = status?.server_time ?? (bot.lastOkAt ?? 0) / 1000;
  const periods: [string, number | null | undefined, boolean][] = [
    ["Bugün", status?.pnl_today.total, false],
    // Raporun `totals` alanı tüm zamanların toplamıdır; bu hafta / bu ay kendi kovasından okunur.
    ["Bu hafta", week.data ? currentPeriodPnl(week.data, nowSeconds) : null, week.loading && !week.data],
    ["Bu ay", month.data ? currentPeriodPnl(month.data, nowSeconds) : null, month.loading && !month.data],
  ];
  const openPnl = bot.positions.reduce((sum, position) => sum + (position.unrealized_pnl ?? 0), 0);
  const activity = summary.data;
  const vetoes = activity ? Object.entries(activity.veto_reasons).sort((a, b) => b[1] - a[1]).slice(0, 3) : [];

  const hero =
    ready && status ? (
      <>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <Text style={{ color: c.white, fontSize: 18, fontWeight: "800" }}>Trade Bot</Text>
          <View testID="mode-pill"><Pill label={status.dry_run ? "DENEME MODU" : "● CANLI"} color={c.white} bg={c.heroSoft} /></View>
        </View>
        <Text style={{ color: c.heroText, fontSize: 14, marginTop: 18 }}>Toplam varlık</Text>
        <Text testID="equity" style={{ color: c.white, fontSize: 40, fontWeight: "900", letterSpacing: -1 }}>{amountText(status.equity, currency)}</Text>
        <Text style={{ color: c.heroText, fontSize: 14 }}>Bakiye {amountText(status.balance, currency)} · Serbest {amountText(status.margin_free, currency)}</Text>
      </>
    ) : (
      <>
        <Text style={{ color: c.white, fontSize: 18, fontWeight: "800" }}>Trade Bot</Text>
        <Text style={{ color: c.heroText, fontSize: 14, marginTop: 18 }}>Toplam varlık</Text>
        <Text style={{ color: c.white, fontSize: 40, fontWeight: "900" }}>—</Text>
      </>
    );

  return (
    <Screen testID="screen-panel" hero={hero}>
      <DataGate>
        {status && state ? (
          <>
            <View style={{ flexDirection: "row", gap: 10 }}>
              {periods.map(([name, value, loading]) => (
                <Card key={name} testID={"pnl-" + name} style={{ flex: 1, padding: 14, gap: 8, borderRadius: 22 }}>
                  <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: soft(value), alignItems: "center", justifyContent: "center" }}>
                    <Ionicons name={(value ?? 0) < 0 ? "trending-down" : "trending-up"} size={17} color={value ? tone(value) : c.muted} />
                  </View>
                  <T muted size={13}>{name}</T>
                  <T weight="900" size={16} style={{ color: tone(value) }}>{loading ? "…" : pnlText(value, null)}</T>
                </Card>
              ))}
            </View>
            <T testID="pnl-caption" muted size={12} style={{ paddingHorizontal: 6 }}>Bugün, açık işlemlerin anlık kâr/zararını da içerir. Bu hafta ve bu ay yalnızca kapanan işlemlerdir (UTC takvimi).</T>
            {week.error || month.error ? <Notice text={"Hafta/ay kâr-zararı alınamadı: " + (week.error || month.error)} /> : null}

            <Card testID="bot-card">
              <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                <IconBubble icon={status.halted || status.stopped ? "pause" : "pulse"} color={stateColor} bg={stateSoft} />
                <View style={{ flex: 1 }}>
                  <T testID="bot-state" weight="800" size={18} style={bot.heartbeatStale ? { color: c.down } : undefined}>{bot.heartbeatStale ? "Bot yanıt vermiyor (son bilinen: " + state.label + ")" : state.label}</T>
                  <T muted size={13}>Son tarama {agoText(status.last_scan_at, nowSeconds)} · Exness {status.stream_connected ? "bağlı" : "kopuk"}</T>
                </View>
              </View>
              <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
                <Pill label={status.open_bot + " bot işlemi"} />
                <Pill label={status.open_manual + " elle işlem"} />
                {bot.positions.length && bot.positions.every((position) => position.unrealized_pnl != null) ? <Pill label={pnlText(openPnl, null) + " açık"} color={tone(openPnl)} bg={soft(openPnl)} /> : null}
              </View>
              {status.halted || status.stopped ? (
                <Button testID="resume" title="Botu devam ettir" icon="play" onPress={() => void resume()} busy={busy} />
              ) : (
                <Button testID="stop" title="Botu durdur" icon="pause" onPress={() => void stop()} busy={busy} />
              )}
              <Button testID="close-all" title="Tüm pozisyonları kapat" kind="dangerText" onPress={() => void closeAll()} disabled={busy} />
              {notice ? <Notice testID="panel-notice" kind={notice.bad ? "bad" : "info"} text={notice.text} /> : null}
            </Card>

            <Card testID="activity-card" style={{ backgroundColor: c.sunSoft, shadowOpacity: 0 }}>
              <T weight="800" size={16}>Son 24 saatte bot</T>
              {activity ? (
                <>
                  <T size={15}>
                    <T weight="900">{activity.scans}</T> tarama yaptı, <T weight="900">{activity.candidates}</T> aday buldu,{" "}
                    {activity.opened > 0 || !activity.dry_run ? (<><T weight="900">{activity.opened}</T> işlem açtı{activity.would_open > 0 ? ", " : "."}</>) : null}
                    {activity.would_open > 0 || (activity.dry_run && activity.opened === 0) ? (<><T weight="900">{activity.would_open}</T> işlem açardı (deneme modu).</>) : null}
                    {" "}{activity.shadowed} gölge kayıt, {activity.news_blocked} haber beklemesi.
                  </T>
                  {vetoes.length ? <T muted size={13}>En sık bekleme nedenleri: {vetoes.map(([reason, count]) => vetoText(reason) + " (" + count + ")").join(" · ")}</T> : null}
                </>
              ) : summary.error ? (
                <T size={14}>Özet alınamadı: {summary.error}</T>
              ) : (
                <T muted size={14}>Özet yükleniyor…</T>
              )}
            </Card>

            <Card testID="mode-card">
              <T weight="800" size={16}>{status.dry_run ? "Deneme modu açık" : "Canlı mod açık"}</T>
              <T muted size={14}>{status.dry_run ? "Bot piyasayı tarıyor ama emir göndermiyor. Canlıya geçince gerçek parayla işlem açar." : "Bot gerçek hesapta işlem açabilir."}</T>
              <Row name="Bugün bot / elle" value={pnlText(status.pnl_today.bot, currency) + " / " + pnlText(status.pnl_today.manual, currency)} />
              {status.dry_run ? (
                <Button testID="go-live" title="Canlı moda geç" kind="tonal" onPress={() => void goLive()} disabled={busy || bot.heartbeatStale} />
              ) : (
                <Button testID="go-dry" title="Deneme moduna dön" kind="tonal" onPress={() => void goDry()} disabled={busy} />
              )}
            </Card>
          </>
        ) : null}
      </DataGate>
    </Screen>
  );
}
