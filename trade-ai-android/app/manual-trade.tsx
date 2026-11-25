import React, { useRef, useState } from "react";
import { Alert } from "react-native";
import * as Crypto from "expo-crypto";
import { BotInput, BotPage, Disconnected } from "../src/bot/BotPage";
import { parsePrice } from "../src/bot/PositionCard";
import { REAL_ACTION_NOTE, amountText, priceText } from "../src/bot/presentation";
import { useBot } from "../src/bot/state";
import { useResource } from "../src/resource";
import type { BotSymbol, TradePreview, TradeRequest } from "../src/bot/types";
import { useTheme } from "../src/theme";
import { Button, Card, Choices, Failure, Heading, Label, Loading, Row, ScreenHeader } from "../src/ui";

const SIDES = { AL: "BUY", SAT: "SELL" } as const;

export default function ManualTrade() {
  const bot = useBot();
  const { colors } = useTheme();
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<keyof typeof SIDES>("AL");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [lots, setLots] = useState("");
  const [preview, setPreview] = useState<TradePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  // Gönderilen emrin kimliği. Sonuç belirsiz kalırsa AYNI kimlikle yeniden sorulur: sunucu ikinci emir açmaz.
  const [pending, setPending] = useState<{ id: string; trade: TradeRequest } | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const sending = useRef(false);
  const ready = bot.phase === "ready";
  const api = bot.api;
  const query = useResource(() => api.symbols(), "symbols:" + (bot.config?.origin ?? ""));
  const symbols: BotSymbol[] | null = query.data ?? null;
  const error = query.error ?? "";
  const load = query.reload;

  const tradable = (symbols ?? []).filter((row) => row.open && row.quoted);

  function request(): TradeRequest | string {
    if (!symbol) return "Bir sembol seçin.";
    const slDistance = parsePrice(sl);
    if (slDistance === undefined || slDistance === null) return "Zarar durdurma mesafesi zorunludur (pozitif sayı).";
    const tpDistance = parsePrice(tp);
    if (tpDistance === null) return "Kâr al mesafesi pozitif bir sayı olmalı.";
    const volume = parsePrice(lots);
    if (volume === null) return "Lot pozitif bir sayı olmalı.";
    return {
      symbol,
      side: SIDES[side],
      sl_distance: slDistance,
      ...(tpDistance !== undefined ? { tp_distance: tpDistance } : {}),
      ...(volume !== undefined ? { lots: volume } : {}),
    };
  }
  function edited<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setPreview(null); // önizleme yalnızca ekrandaki değerler için geçerlidir
    };
  }
  async function runPreview() {
    const trade = request();
    if (typeof trade === "string") return setNotice({ text: trade, bad: true });
    setBusy(true);
    setNotice(null);
    try {
      setPreview(await api.previewTrade(trade));
    } catch (reason) {
      setPreview(null);
      setNotice({ text: reason instanceof Error ? reason.message : "Önizleme alınamadı.", bad: true });
    } finally {
      setBusy(false);
    }
  }
  async function send(id: string, trade: TradeRequest) {
    if (sending.current) return; // çift dokunuş aynı emri iki kez göndermesin
    sending.current = true;
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.openTrade(trade, id);
      setPending(null);
      setUncertain(false);
      setPreview(null);
      setNotice({
        text: (result.duplicate ? "Emir daha önce alınmış: " : "Emir gönderildi: ") + priceText(result.lots) + " lot. Pozisyonlar sekmesinden izleyin.",
        bad: false,
      });
    } catch (reason) {
      const unknown = reason instanceof Error && "uncertain" in reason && (reason as { uncertain: boolean }).uncertain;
      setUncertain(unknown);
      if (!unknown) setPending(null);
      setNotice({ text: reason instanceof Error ? reason.message : "Emir gönderilemedi.", bad: true });
    } finally {
      sending.current = false;
      setBusy(false);
      void bot.refresh();
    }
  }
  function confirmSend() {
    const trade = request();
    if (typeof trade === "string" || !preview) return;
    // Onaylanan lot, önizlemede gösterilen lottur.
    const order: TradeRequest = { ...trade, lots: preview.lots };
    Alert.alert(
      symbol + " " + side + " emri gönderilsin mi?",
      [
        priceText(preview.lots) + " lot, piyasa fiyatından",
        "Zarar durdur: " + priceText(preview.sl) + " (en çok −" + amountText(preview.loss, preview.currency) + ")",
        preview.tp != null ? "Kâr al: " + priceText(preview.tp) : "Kâr al yok",
        ...preview.warnings.map((warning) => "⚠ " + warning),
      ].join("\n") + (bot.status?.dry_run ? "\n\n" + REAL_ACTION_NOTE : "\n\nBu emir GERÇEK hesapta açılır."),
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Emri gönder",
          style: "destructive",
          onPress: () => {
            const id = Crypto.randomUUID();
            setPending({ id, trade: order });
            void send(id, order);
          },
        },
      ],
    );
  }

  return (
    <BotPage>
      <ScreenHeader title="Elle işlem" badge="TRADE BOT" subtitle="Botun sınırlarına sayılmaz; lot hesabı gerçek varlığınızla yapılır." />
      <Disconnected />
      {ready ? (
        <>
          {error ? <Failure message={"Semboller alınamadı. " + error} retry={load} /> : null}
          {symbols === null ? (
            error ? null : <Loading />
          ) : tradable.length === 0 ? (
            <Card>
              <Label>Şu an işleme açık ve fiyatı güncel sembol yok.</Label>
            </Card>
          ) : (
            <Card>
              <Heading>Sembol</Heading>
              <Choices values={tradable.map((row) => row.symbol)} value={symbol} onChange={edited(setSymbol)} />
              <Heading>Yön</Heading>
              <Choices values={Object.keys(SIDES) as (keyof typeof SIDES)[]} value={side} onChange={edited(setSide)} />
              <BotInput accessibilityLabel="Zarar durdurma mesafesi" placeholder="SL mesafesi (fiyat farkı, zorunlu)" keyboardType="decimal-pad" editable={!busy} value={sl} onChangeText={edited(setSl)} />
              <BotInput accessibilityLabel="Kâr al mesafesi" placeholder="TP mesafesi (isteğe bağlı)" keyboardType="decimal-pad" editable={!busy} value={tp} onChangeText={edited(setTp)} />
              <BotInput accessibilityLabel="Lot" placeholder="Lot (boşsa risk yüzdesine göre önerilir)" keyboardType="decimal-pad" editable={!busy} value={lots} onChangeText={edited(setLots)} />
              <Button title="Önizle" onPress={() => void runPreview()} disabled={busy || uncertain} secondary />
            </Card>
          )}
          {preview ? (
            <Card>
              <Heading>Önizleme</Heading>
              <Row name="Lot" value={priceText(preview.lots) + (preview.lots !== preview.suggested_lots ? " (öneri: " + priceText(preview.suggested_lots) + ")" : "")} />
              <Row name="Giriş (yaklaşık)" value={priceText(preview.entry)} />
              <Row name="Zarar durdur" value={priceText(preview.sl)} />
              <Row name="Kâr al" value={priceText(preview.tp)} />
              <Row name="En çok zarar" value={"−" + amountText(preview.loss, preview.currency) + (preview.loss_pct != null ? " (%" + String(Number(preview.loss_pct.toFixed(2))).replace(".", ",") + ")" : "")} />
              <Row name="Olası kâr" value={preview.profit != null ? "+" + amountText(preview.profit, preview.currency) : "—"} />
              {preview.warnings.map((warning) => (
                <Label key={warning} style={{ color: colors.red }}>⚠ {warning}</Label>
              ))}
              <Button title="Emri gönder" onPress={confirmSend} disabled={busy || uncertain} />
            </Card>
          ) : null}
          {uncertain && pending ? (
            <Card elevated>
              <Label style={{ color: colors.red, fontWeight: "700" }}>Emrin sonucu bilinmiyor</Label>
              <Label muted>Yeni emir göndermeyin. Aşağıdaki düğme aynı emrin durumunu sorar; ikinci bir emir açmaz.</Label>
              <Button
                title="Sonucu kontrol et"
                onPress={() => void send(pending.id, pending.trade)}
                disabled={busy}
                secondary
              />
            </Card>
          ) : null}
          {notice ? <Label style={{ color: notice.bad ? colors.red : colors.muted }}>{notice.text}</Label> : null}
        </>
      ) : null}
    </BotPage>
  );
}
