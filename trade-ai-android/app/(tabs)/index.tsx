import React, { useRef, useState } from "react";
import { Alert } from "react-native";
import { BotPage, Disconnected, NoData, StaleNotice } from "../../src/bot/BotPage";
import { REAL_ACTION_NOTE, agoText, amountText, botStateText, pnlText } from "../../src/bot/presentation";
import { useBot } from "../../src/bot/state";
import { useTheme } from "../../src/theme";
import { Button, Card, Heading, Label, Row, ScreenHeader } from "../../src/ui";

export default function Panel() {
  const bot = useBot();
  const { colors } = useTheme();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  const status = bot.status;

  const running = useRef(false); // çift dokunuş aynı emri iki kez göndermesin
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
  function confirmStop() {
    Alert.alert(
      "Bot durdurulsun mu?",
      "Yeni işlem açılmaz. Açık işlemler zarar durdurmalarıyla birlikte yönetilmeye devam eder.",
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Durdur", style: "destructive", onPress: () => void run(() => bot.api.stop(), "Bot durduruldu.") },
      ],
    );
  }
  function confirmResume() {
    if (!status?.halted) {
      Alert.alert("Bot devam etsin mi?", "Bot yeniden işlem açabilir.", [
        { text: "Vazgeç", style: "cancel" },
        { text: "Devam et", onPress: () => void run(() => bot.api.resume(false), "Bot devam ediyor.") },
      ]);
      return;
    }
    // Bot kendini kayıp sınırı yüzünden durdurdu: iki ayrı onay istenir.
    Alert.alert(
      "Bot kayıp sınırı nedeniyle durdu",
      "Neden: " +
        (status.halt_reason || "toplam kayıp sınırı") +
        ".\n\nDevam ederseniz kayıp ölçümü şimdiki bakiyeden yeniden başlar ve bot yeni işlem açabilir.",
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Devam etmek istiyorum",
          style: "destructive",
          onPress: () =>
            Alert.alert("Emin misiniz?", "Kayıp sınırı koruması sıfırlanacak.", [
              { text: "Vazgeç", style: "cancel" },
              {
                text: "Evet, devam et",
                style: "destructive",
                onPress: () => void run(() => bot.api.resume(true), "Bot devam ediyor."),
              },
            ]),
        },
      ],
    );
  }
  function confirmCloseAll() {
    const count = (status?.open_bot ?? 0) + (status?.open_manual ?? 0);
    Alert.alert(
      "Tüm pozisyonlar kapatılsın mı?",
      (count > 0
        ? "Bot ve elle açılmış " + count + " pozisyonun tamamı piyasa fiyatından kapatılır ve bot durdurulur."
        : "Açık pozisyon görünmüyor; yine de varsa hepsi kapatılır ve bot durdurulur.") +
        " Bu işlem geri alınamaz." +
        (status?.dry_run ? "\n\n" + REAL_ACTION_NOTE : ""),
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Hepsini kapat",
          style: "destructive",
          onPress: () =>
            void run(async () => {
              const result = await bot.api.closeAll();
              if (result.skipped?.length)
                throw new Error(
                  result.requested +
                    " pozisyon için kapama istendi; " +
                    result.skipped.length +
                    " pozisyonda zaten bekleyen bir kapama var. Pozisyonlar sekmesinden kontrol edin.",
                );
            }, "Kapama istekleri gönderildi. Pozisyonlar sekmesinden izleyin."),
        },
      ],
    );
  }

  if (bot.phase !== "ready")
    return (
      <BotPage>
        <ScreenHeader title="Panel" badge="TRADE BOT" />
        <Disconnected />
      </BotPage>
    );

  const state = status ? botStateText(status) : null;
  const toneColor = { ok: colors.green, warn: colors.gold, bad: colors.red };
  const currency = status?.currency;
  // Süreler sunucu saatine göre hesaplanır; eski sunucularda son yanıt anı kullanılır.
  const nowSeconds = status?.server_time ?? (bot.lastOkAt ?? 0) / 1000;
  return (
    <BotPage>
      <ScreenHeader title="Panel" badge="TRADE BOT" />
      <StaleNotice />
      <NoData />
      {!status || !state ? null : (
        <>
          <Card>
            <Heading>Bot durumu</Heading>
            {bot.heartbeatStale ? (
              <Label style={{ color: colors.red, fontWeight: "700" }}>
                Bot yanıt vermiyor (son bilinen durum: {state.label})
              </Label>
            ) : (
              <Label style={{ color: toneColor[state.tone], fontWeight: "700" }}>{state.label}</Label>
            )}
            <Row name="Son tarama" value={agoText(status.last_scan_at, nowSeconds)} />
            <Row name="Exness bağlantısı" value={status.stream_connected ? "Bağlı" : "Kopuk"} />
          </Card>
          <Card>
            <Heading>Hesap</Heading>
            <Row name="Bakiye" value={amountText(status.balance, currency)} />
            <Row name="Varlık (equity)" value={amountText(status.equity, currency)} />
            <Row name="Serbest teminat" value={amountText(status.margin_free, currency)} />
          </Card>
          <Card>
            <Heading>Bugünkü kâr/zarar</Heading>
            <Row name="Bot" value={pnlText(status.pnl_today.bot, currency)} />
            <Row name="Elle" value={pnlText(status.pnl_today.manual, currency)} />
            <Row name="Toplam" value={pnlText(status.pnl_today.total, currency)} />
            <Label muted style={{ fontSize: 12 }}>
              Açık işlemlerin anlık kârı/zararı dahildir. Gün Türkiye saatiyle 03:00’te başlar.
            </Label>
          </Card>
          <Card>
            <Heading>Açık işlemler</Heading>
            <Row name="Bot işlemleri" value={String(status.open_bot)} />
            <Row name="Elle işlemler" value={String(status.open_manual)} />
          </Card>
          <Card>
            <Heading>Kontrol</Heading>
            {status.halted || status.stopped ? (
              <Button title="Devam" onPress={confirmResume} disabled={busy} />
            ) : (
              <Button title="Durdur" onPress={confirmStop} disabled={busy} secondary />
            )}
            <Button title="Hepsini kapat" onPress={confirmCloseAll} disabled={busy} secondary />
            {notice ? (
              <Label style={{ color: notice.bad ? colors.red : colors.muted }}>{notice.text}</Label>
            ) : null}
          </Card>
        </>
      )}
    </BotPage>
  );
}
