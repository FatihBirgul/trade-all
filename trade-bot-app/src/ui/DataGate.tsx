import React, { type PropsWithChildren } from "react";
import { router } from "expo-router";
import { useBot } from "../bot/state";
import { clockText } from "../bot/presentation";
import { Button, Empty, Failure, Loading, Notice } from "./kit";

// Bot verisine bağlı ekranların ortak kapısı: bağlantı yok / ilk veri bekleniyor / hiç veri alınamadı.
// Veri varsa çocuklar çizilir; üstte bayatlık ve hata uyarıları ayrıca gösterilir.
export function DataGate({ children }: PropsWithChildren) {
  const bot = useBot();
  if (bot.phase === "loading") return <Loading label="Bağlantı bilgisi okunuyor…" />;
  if (bot.phase !== "ready")
    return (
      <Empty
        icon="link"
        title={bot.phase === "revoked" ? "Bu telefonun bağlantısı iptal edilmiş" : "Sunucuya bağlı değilsiniz"}
        text="Botu izlemek ve yönetmek için telefonu sunucuyla eşleştirin."
      >
        <Button testID="open-connection" title="Bağlantı ekranını aç" icon="link" onPress={() => router.push("/connection")} />
      </Empty>
    );
  if (bot.lastOkAt === null)
    return bot.error ? <Failure message={bot.error} retry={() => void bot.refresh()} /> : <Loading label="Sunucudan veri bekleniyor…" />;
  return (
    <>
      {bot.heartbeatStale ? (
        <Notice testID="notice-stale" kind="bad" text={"Bottan 5 dakikadır haber yok. Aşağıdaki bilgiler eski olabilir (son güncelleme " + clockText(bot.lastOkAt) + "). Açık pozisyonların zarar durdurma emirleri Exness tarafında durur."} />
      ) : bot.error ? (
        <Notice testID="notice-error" text={bot.error + " Son bilinen bilgiler gösteriliyor (" + clockText(bot.lastOkAt) + ")."} />
      ) : null}
      {children}
    </>
  );
}
