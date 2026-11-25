import React, { useState } from "react";
import { Alert, Switch, View } from "react-native";
import { Button, Card, Heading, Label, Row } from "../ui";
import { useTheme } from "../theme";
import { BotInput } from "./BotPage";
import { pnlText, pnlTone, priceText } from "./presentation";
import type { BotApi } from "./client";
import type { BotPosition, PositionPatch } from "./types";

// "1,0972" ya da "1.0972" -> sayı. Boş -> undefined (alan gönderilmez). Geçersiz -> null.
export function parsePrice(text: string): number | undefined | null {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  if (!/^[0-9]+([.,][0-9]+)?$/.test(trimmed)) return null;
  const value = Number(trimmed.replace(",", "."));
  return Number.isFinite(value) && value > 0 ? value : null;
}

type Props = {
  position: BotPosition;
  currency: string | null | undefined;
  api: Pick<BotApi, "closePosition" | "patchPosition">;
  onChanged: () => void;
};

export function PositionCard({ position, currency, api, onChanged }: Props) {
  const { colors } = useTheme();
  const [editing, setEditing] = useState(false);
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  const tone = pnlTone(position.unrealized_pnl);
  const pnlColor = tone === "ok" ? colors.green : tone === "bad" ? colors.red : colors.text;

  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice({ text: done, bad: false });
      return true;
    } catch (reason) {
      // 409/422: sunucunun kendi açıklaması; ağ hatası: "sonuç belirsiz" uyarısı.
      setNotice({ text: reason instanceof Error ? reason.message : "İşlem tamamlanamadı.", bad: true });
      return false;
    } finally {
      setBusy(false);
      onChanged();
    }
  }
  function confirmClose() {
    Alert.alert(
      position.symbol + " kapatılsın mı?",
      priceText(position.volume) + " lot piyasa fiyatından kapatılır. Bu işlem geri alınamaz.",
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Kapat",
          style: "destructive",
          onPress: () => void run(() => api.closePosition(position.position_id), "Kapama isteği gönderildi."),
        },
      ],
    );
  }
  async function save() {
    const nextSl = parsePrice(sl);
    const nextTp = parsePrice(tp);
    if (nextSl === null || nextTp === null) {
      setNotice({ text: (nextSl === null ? "SL" : "TP") + " pozitif bir sayı olmalı.", bad: true });
      return;
    }
    const patch: PositionPatch = {};
    if (nextSl !== undefined && nextSl !== position.sl) patch.sl = nextSl;
    if (nextTp !== undefined && nextTp !== position.tp1) patch.tp = nextTp;
    if (patch.sl === undefined && patch.tp === undefined) {
      setNotice({ text: "Değişiklik yok.", bad: false });
      return;
    }
    if (await run(() => api.patchPosition(position.position_id, patch), "Değişiklik isteği gönderildi.")) {
      setEditing(false);
      setSl("");
      setTp("");
    }
  }

  return (
    <Card>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <Heading>
          {position.symbol} · {position.side === "BUY" ? "AL" : "SAT"}
        </Heading>
        <Label muted style={{ fontSize: 12, fontWeight: "700" }}>
          {position.origin === "bot" ? "Bot" : "Elle"}
        </Label>
      </View>
      <Label style={{ color: pnlColor, fontWeight: "700", fontSize: 18, lineHeight: 24 }}>
        {pnlText(position.unrealized_pnl, currency)}
        {position.r_multiple != null
          ? "  ·  " + (position.r_multiple >= 0 ? "+" : "−") + priceText(Math.abs(Number(position.r_multiple.toFixed(2)))) + "R"
          : ""}
      </Label>
      <Row name="Lot" value={priceText(position.volume)} />
      <Row name="Giriş" value={priceText(position.entry)} />
      <Row name="Anlık fiyat" value={priceText(position.price)} />
      <Row name="Zarar durdur (SL)" value={priceText(position.sl)} />
      <Row name="Kâr al (TP)" value={priceText(position.tp1)} />
      {position.tp2 != null ? <Row name="İkinci hedef" value={priceText(position.tp2)} /> : null}
      {position.sl == null ? (
        <Label style={{ color: colors.red, fontWeight: "700" }}>
          Bu pozisyonda zarar durdurma görünmüyor. Hemen bir SL girin ya da pozisyonu kapatın.
        </Label>
      ) : null}
      {position.user_sl_override ? <Label muted>SL kullanıcı tarafından ayarlandı</Label> : null}
      {position.be_done ? <Label muted>SL giriş seviyesine çekildi</Label> : null}
      {position.partial_done ? <Label muted>Kısmi kâr alındı</Label> : null}
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 48 }}>
        <Label>Kademeli stop</Label>
        <Switch
          accessibilityLabel={"Kademeli stop " + position.symbol}
          value={position.manage}
          disabled={busy}
          onValueChange={(value) =>
            void run(
              () => api.patchPosition(position.position_id, { manage: value }),
              value ? "Kademeli stop açıldı." : "Kademeli stop kapatıldı.",
            )
          }
        />
      </View>
      {editing ? (
        <>
          <BotInput
            accessibilityLabel={"Yeni SL " + position.symbol}
            placeholder={"Yeni SL (şimdiki: " + priceText(position.sl) + ")"}
            keyboardType="decimal-pad"
            editable={!busy}
            value={sl}
            onChangeText={setSl}
          />
          <BotInput
            accessibilityLabel={"Yeni TP " + position.symbol}
            placeholder={"Yeni TP (şimdiki: " + priceText(position.tp1) + ")"}
            keyboardType="decimal-pad"
            editable={!busy}
            value={tp}
            onChangeText={setTp}
          />
          <Label muted>Boş bıraktığınız alan değişmez. Buradan verdiğiniz SL’yi bot zarar yönüne geri almaz.</Label>
          <Button title="Kaydet" onPress={() => void save()} disabled={busy} />
          <Button title="Vazgeç" onPress={() => setEditing(false)} disabled={busy} variant="ghost" />
        </>
      ) : (
        <Button title="SL/TP düzenle" onPress={() => setEditing(true)} disabled={busy} secondary />
      )}
      <Button title="Kapat" onPress={confirmClose} disabled={busy} secondary />
      {notice ? <Label style={{ color: notice.bad ? colors.red : colors.muted }}>{notice.text}</Label> : null}
    </Card>
  );
}
