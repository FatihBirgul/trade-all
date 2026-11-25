import React from "react";
import { BotPage, Disconnected, NoData, StaleNotice } from "../../src/bot/BotPage";
import { PositionCard } from "../../src/bot/PositionCard";
import { useBot } from "../../src/bot/state";
import { router } from "expo-router";
import { Button, Empty, ScreenHeader } from "../../src/ui";

export default function Positions() {
  const bot = useBot();
  const ready = bot.phase === "ready";
  return (
    <BotPage>
      <ScreenHeader
        title="Pozisyonlar"
        badge="TRADE BOT"
        subtitle={ready && bot.lastOkAt !== null ? bot.positions.length + " açık pozisyon" : undefined}
      />
      <Disconnected />
      {ready ? (
        <>
          <StaleNotice />
          <Button title="Elle işlem aç" onPress={() => router.push("/manual-trade")} secondary />
          <NoData />
          {bot.lastOkAt === null ? null : bot.positions.length === 0 ? (
            <Empty text="Açık pozisyon yok." />
          ) : (
            bot.positions.map((position) => (
              <PositionCard
                key={position.position_id}
                position={position}
                currency={bot.status?.currency}
                dryRun={bot.status?.dry_run ?? false}
                api={bot.api}
                onChanged={() => void bot.refresh()}
              />
            ))
          )}
        </>
      ) : null}
    </BotPage>
  );
}
